#!/usr/bin/env python3
"""Find token accounting that silently undercounts Anthropic's prompt cache.

Anthropic reports `input_tokens` NET of the prompt cache and bills
`cache_read_input_tokens` and `cache_creation_input_tokens` separately on top. It does not
send a total. So code that computes one as input + output charges its users for a number
smaller than the one the provider billed, and nothing raises.

That defect has been found by hand in five independent agent frameworks: Pipecat, LiveKit
Agents, LlamaIndex, Haystack and mcp-use. This is the check that would have found each of
them in a second.

    python cachecheck.py path/to/repo
    python cachecheck.py . --json
    python cachecheck.py . --quiet     # exit code only, for CI

Exit code is 1 when anything is found, so it works as a CI gate.

WHAT IT DELIBERATELY DOES NOT FLAG

OpenAI reports `cached_tokens` INSIDE `prompt_tokens`. Adding it there would double count.
A file that only handles OpenAI-shaped usage is correct as written, and flagging it would be
the same class of error in the opposite direction.

Comments, docstrings and type declarations name these fields without computing anything. An
earlier version flagged `inputTokens?: number;` and a docstring showing sample output, which
is the kind of noise that gets a checker switched off. Rule 2 requires evidence of
arithmetic, not a mention.
"""

import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".jsx", ".go", ".rb", ".java", ".kt")
SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "dist", "build", "__pycache__",
    ".next", ".turbo", "vendor", "target", ".mypy_cache", ".pytest_cache",
}

CACHE_READ = re.compile(r"cache_read_input_tokens|cacheReadInputTokens", re.I)
CACHE_WRITE = re.compile(r"cache_creation_input_tokens|cacheCreationInputTokens", re.I)

SUMS = [
    re.compile(r"input_tokens\s*\+\s*output_tokens"),
    re.compile(r"output_tokens\s*\+\s*input_tokens"),
    re.compile(r"prompt_tokens\s*\+\s*completion_tokens"),
    re.compile(r"completion_tokens\s*\+\s*prompt_tokens"),
    re.compile(r"inputTokens\s*\+\s*outputTokens"),
    re.compile(r"outputTokens\s*\+\s*inputTokens"),
    re.compile(r"promptTokens\s*\+\s*completionTokens"),
]

ANTHROPIC = re.compile(r"anthropic|claude-[0-9a-z]|bedrock|input_tokens|inputTokens", re.I)
OPENAI_SHAPED = re.compile(
    r"prompt_tokens_details|promptTokensDetails|input_tokens_details|cached_tokens", re.I
)
READS_INPUT = re.compile(r"input_tokens|inputTokens")

# Evidence the file does something with the number rather than merely naming it.
USES_ARITHMETICALLY = re.compile(
    r"(input_tokens|inputTokens|prompt_tokens|promptTokens)\s*[-+*/]"
    r"|[-+*/]\s*(input_tokens|inputTokens|prompt_tokens|promptTokens)"
    r"|(total|sum|cost|price|billed|usage)\w*\s*[:=][^\n;]*"
    r"(input_tokens|inputTokens|prompt_tokens|promptTokens)",
    re.I,
)

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"^[ \t]*(//|#).*$", re.M)
PY_DOCSTRING = re.compile(r'("{3}|\x27{3}).*?\1', re.S)


def strip_noise(text, path):
    """Remove comments and docstrings. They name fields without computing anything."""
    text = BLOCK_COMMENT.sub(" ", text)
    text = LINE_COMMENT.sub(" ", text)
    if path.endswith(".py"):
        text = PY_DOCSTRING.sub(" ", text)
    return text


def is_openai_shaped(text):
    """True when the cache handling is OpenAI's, where the cache is already inside."""
    return bool(OPENAI_SHAPED.search(text)) and not CACHE_READ.search(text)


# Test fixtures construct usage objects; they do not bill anyone. Both false positives in
# the first validated run were a conftest and a .test.ts. Skipped by default, --tests to keep.
TEST_PATH = re.compile(r"(^|[\/])(tests?|__tests__|spec|fixtures)([\/]|$)|"
                       r"(^|[\/])(test_[^\/]*|conftest)\.py$|"
                       r"\.(test|spec)\.[jt]sx?$", re.I)


def walk(root):
    if os.path.isfile(root):
        yield root
        return
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if name.endswith(SUFFIXES):
                yield os.path.join(base, name)


def check_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError:
        return []
    if not ANTHROPIC.search(raw):
        return []

    code = strip_noise(raw, path)
    if not READS_INPUT.search(code):
        return []

    findings = []
    lines = raw.split("\n")
    has_read = bool(CACHE_READ.search(code))
    has_write = bool(CACHE_WRITE.search(code))
    openai_only = is_openai_shaped(code)

    def line_of(offset_text, match):
        return offset_text[:match.start()].count("\n") + 1

    # 1. A total that cannot include the cache, in a file that knows about Anthropic.
    if not has_read and not openai_only:
        for i, line in enumerate(lines, 1):
            if LINE_COMMENT.match(line):
                continue
            for rx in SUMS:
                if rx.search(line):
                    findings.append({
                        "rule": "cache-blind-total",
                        "path": path, "line": i, "evidence": line.strip()[:120],
                        "why": "totals input plus output, and this file never reads "
                               "cache_read_input_tokens. On Anthropic those tokens are "
                               "billed and are not inside input_tokens.",
                    })
                    break

    # 2. Computes with Anthropic usage and never reads the cache counter at all.
    if not has_read and not openai_only:
        m = USES_ARITHMETICALLY.search(code)
        if m:
            findings.append({
                "rule": "cache-read-never-read",
                "path": path, "line": line_of(code, m),
                "evidence": m.group(0).strip()[:120],
                "why": "computes with input_tokens and never reads "
                       "cache_read_input_tokens, so every token served from cache is "
                       "invisible to this accounting.",
            })

    # 3. Handles cache reads but not cache writes, which Anthropic bills above base rate.
    if has_read and not has_write:
        m = CACHE_READ.search(code)
        findings.append({
            "rule": "cache-creation-ignored",
            "path": path, "line": line_of(code, m),
            "evidence": m.group(0)[:120],
            "why": "reads cache_read_input_tokens but never "
                   "cache_creation_input_tokens. Cache writes are billed above the "
                   "base rate, so they cost more per token than the ones remembered.",
        })
    return findings


def main():
    ap = argparse.ArgumentParser(description="Find token accounting blind to Anthropic's prompt cache.")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--tests", action="store_true",
                    help="also scan test files, which normally only build fixtures")
    args = ap.parse_args()

    findings, scanned = [], 0
    for path in walk(args.root):
        # Normalise the separator first. The pattern is written with forward slashes and
        # os.path.join produces backslashes on Windows, so tests/conftest.py was being
        # scanned there and skipped everywhere else. Same rule, either platform.
        if not args.tests and TEST_PATH.search(path.replace(chr(92), "/")):
            continue
        scanned += 1
        findings += check_file(path)

    if args.as_json:
        print(json.dumps({"scanned": scanned, "findings": findings}, indent=2))
        return 1 if findings else 0
    if args.quiet:
        return 1 if findings else 0

    if not findings:
        print(f"Scanned {scanned} files. Nothing found.")
        print("That is a result, not a failure to look: every total in this tree already")
        print("accounts for the prompt cache, or the file is OpenAI-shaped where the cache")
        print("is already inside prompt_tokens.")
        return 0

    by_rule = {}
    for f in findings:
        by_rule.setdefault(f["rule"], []).append(f)

    print(f"Scanned {scanned} files. {len(findings)} findings.\n")
    for rule, group in by_rule.items():
        print("=" * 78)
        print(f"{rule}  ({len(group)})")
        print("=" * 78)
        print(f"  {group[0]['why']}\n")
        for f in group:
            try:
                rel = os.path.relpath(f["path"], args.root)
            except ValueError:
                rel = f["path"]
            print(f"  {rel}:{f['line']}")
            print(f"      {f['evidence']}")
        print()
    print("Every rule here comes from a defect found by hand in a shipped library, each")
    print("with a pull request and a test that fails on main:")
    print("  https://github.com/arthi-arumugam-git/wrong-numbers")
    return 1


if __name__ == "__main__":
    sys.exit(main())
