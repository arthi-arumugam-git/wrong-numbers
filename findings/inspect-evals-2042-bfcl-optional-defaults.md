# BFCL scores an optional parameter at its own default as a disagreement

**Library:** UKGovernmentBEIS/inspect_evals · **PR:** [#2042](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2042)
· **Status:** merged 2026-07-31 · Fixes [#2004](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2004)

**Credit:** the defect and the three `exec_simple` examples are
[@wise-east's, in issue #2004](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2004).
What is mine is confirming all three against the pinned dataset, the sweep that measured how
far it reaches, the fix, and the tests.

## What's wrong

The AST scorer holds the function schema in `func_description` but never reads parameter
defaults. An optional parameter sitting at its default is therefore scored as a disagreement
in both directions:

| | ground truth | model | scored |
|---|---|---|---|
| A | omits the parameter | states it at the default | `Unexpected parameter` |
| B | states it at exactly the default | omits it | `Missing parameter` |

Neither is a real disagreement. The two calls are equivalent. Accuracy comes out low and
nothing raises, which is the whole shape of this class: the scorer returns a number that is
the right type and a plausible value, and no part of the pipeline is in a position to notice
it is wrong.

## The number

Swept every ground truth in the eight AST categories that are actually scored this way, since
`exec_simple` is an execution category living in `unused_datasets`:

| category | items | A: gt omits | B: gt states default | boundary |
|---|---|---|---|---|
| simple_python | 400 | 0 | 1 | 22 |
| simple_java | 100 | 0 | 0 | 0 |
| simple_javascript | 50 | 0 | 0 | 0 |
| multiple | 200 | 0 | 0 | 9 |
| parallel | 200 | 0 | 1 | 66 |
| parallel_multiple | 200 | 1 | 1 | 55 |
| live_simple | 258 | 0 | 2 | 123 |
| live_multiple | 1053 | 32 | 23 | 1006 |
| **total** | | **33** | **28** | **1281** |

61 parameter occurrences where an equivalent call is scored as a disagreement. For example
`run_two_sample_ttest(equal_variance=True)` in `simple_python_120` and
`get_tickets(status='open')` in `live_simple_124-80-0`, both pinning a parameter to its own
declared default.

## The boundary is 21x larger than the bug

The 1281 matters more than the 61. Those are the cases where an optional parameter has a
default and the ground truth states a value that is **not** it, so omission genuinely differs
and must keep scoring as wrong. Item 78 is the clean example: `sort_array`'s `reverse` defaults
to `false` and the ground truth passes `reverse=True`, so leaving it out is a real
disagreement.

A fix that simply ignored optional parameters would clear the 61 and silently break 1281,
which is the same failure mode as the original bug and 21 times bigger. This is the recurring
trap in this write-up: the obvious fix is usually wrong in the same direction as the defect.

## Reproduce

- Source: `src/inspect_evals/bfcl/`
- Test: `tests/bfcl/test_scorer.py`

```bash
gh pr checkout 2042 --repo UKGovernmentBEIS/inspect_evals
python -m pytest tests/bfcl/test_scorer.py -q
```

Seven cases, using the real schemas from items 86, 79 and 78. Two fail on `main` with exactly
the reported errors:

```
test_explicit_default_accepted_when_ground_truth_omits_it     fails on main: Unexpected parameter: adjust_for_inflation
test_omission_accepted_when_ground_truth_states_the_default   fails on main: Missing parameter: reverse
test_explicit_non_default_still_unexpected                    guard
test_parameter_absent_from_schema_still_unexpected            guard
test_omission_rejected_when_ground_truth_states_a_non_default guard, item 78
test_required_parameter_never_treated_as_defaulted            guard
test_no_schema_default_leaves_behaviour_unchanged             guard
```

The five guards pass before and after, which is the point of including them: they pin the
1281 boundary cases that the naive fix would have broken.

`tests/bfcl/`: 331 passed, 25 skipped, 3 xfailed. `ruff format`, `ruff check` and `mypy`
clean. `tests/bfcl/test_backend_loader.py::test_all_backend_classes_importable` fails on a
clean checkout of `main` too (`MathAPI`), so it was left alone.

## Deliberately not included

The eval version goes `5-B` to `6-B`, since reported results change for any run. README
changelog and fragment are in the PR. The other READMEs were not regenerated:
`tools/generate_readmes.py` rewrites 38 files on a clean `main` and none of those changes
belong to this PR.
