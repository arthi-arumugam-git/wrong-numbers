#!/usr/bin/env python3
"""Is the code that computes an eval's number covered by any test?

Run it against one or more checked-out repositories:

    python research/audit_metric_coverage.py path/to/repo [path/to/repo ...]

Method, applied identically to every repository:

  1. Collect every top-level ``def``/``class`` that either lives in a
     metric/scorer module (path contains metrics/, metric/, scorers/, scorer/,
     scoring/, evaluation/) or whose name marks it as producing a number
     (*_score, *_metric, *_rate, *_stderr, score_*, metric_*, accuracy,
     precision, recall, f1*, aggregate_*, compute_*).
  2. Ask whether that identifier appears anywhere in any test file.

Step 2 is deliberately generous. Being named in a test is not the same as
being tested: a name can appear in an import, a fixture, or an end-to-end run
that never asserts on the number. So every figure this prints is a LOWER BOUND
on how much metric code is unexercised. Private helpers are excluded.

Known limitation, stated because the point of this repository is that
unstated assumptions produce wrong numbers: the heuristic is approximate
across frameworks, and a framework that tests metrics only through
integration runs will look worse here than it is. As a check, running the
strict variant on inspect_evals (``@metric``-decorated functions only) gives
42%, against 44% for this heuristic. Two independent definitions, two points
apart.
"""

from __future__ import annotations

import pathlib
import re
import sys

METRIC_MODULE = re.compile(r"(^|/)(metrics?|scorers?|scoring|evaluation)(/|\.py$)")
METRIC_NAME = re.compile(
    r"(_score|_metric|_rate|_stderr|^score_|^metric_|accuracy|precision"
    r"|recall|^f1|aggregate_|^compute_)",
    re.IGNORECASE,
)
TEST_FILE = re.compile(
    r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_test\.py$|conftest\.py$"
)


def audit(root: pathlib.Path) -> tuple[dict[str, str], dict[str, str]]:
    definitions: list[tuple[str, str]] = []
    test_sources: list[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if TEST_FILE.search(rel):
            test_sources.append(text)
            continue
        in_metric_module = bool(METRIC_MODULE.search(rel))
        for match in re.finditer(r"^(?:class|def|async def)\s+(\w+)", text, re.M):
            name = match.group(1)
            if name.startswith("_"):
                continue
            if in_metric_module or METRIC_NAME.search(name):
                definitions.append((name, rel))
    named_in_tests = set(re.findall(r"\w+", "\n".join(test_sources)))
    unique: dict[str, str] = {}
    for name, rel in definitions:
        unique.setdefault(name, rel)
    untested = {n: f for n, f in unique.items() if n not in named_in_tests}
    return unique, untested


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    rows = []
    for arg in argv:
        root = pathlib.Path(arg)
        if not root.is_dir():
            print(f"skipping {arg}: not a directory", file=sys.stderr)
            continue
        found, untested = audit(root)
        if found:
            rows.append((root.name, len(found), len(untested)))
    if not rows:
        return 1
    print(f"{'framework':26}{'defs':>8}{'never named in a test':>24}{'rate':>8}")
    print("-" * 66)
    total = total_untested = 0
    for name, found, untested in sorted(rows, key=lambda r: -(r[2] / max(r[1], 1))):
        total += found
        total_untested += untested
        print(f"{name:26}{found:8}{untested:24}{untested / found * 100:7.0f}%")
    print("-" * 66)
    print(f"{'TOTAL':26}{total:8}{total_untested:24}{total_untested / total * 100:7.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
