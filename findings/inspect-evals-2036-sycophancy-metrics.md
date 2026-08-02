# Sycophancy's `confidence` and `apologize_rate` report 0.0 on every run

**Library:** UKGovernmentBEIS/inspect_evals · **PR:** [#2036](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2036)
· **Status:** merged 2026-07-31

**Credit:** the diagnosis is [@dewstend's, in issue #1979](https://github.com/UKGovernmentBEIS/inspect_evals/issues/1979),
and it is correct about the mechanism. What is mine is the fix, the demonstration that the
fix the issue proposes reports a different wrong number, the repo-wide sweep and the tests.

## What's wrong

`confidence` and `apologize_rate` are registered under a metrics dict key. inspect_ai then
replaces `Score.value` with just that key's extracted float, so the `isinstance(value, dict)`
branch inside each metric never runs. Both return 0.0, on every run, for every model.

## The number

Four samples, three answered correctly, of those three the model apologizes twice:

| metric | main | fixed | correct |
|---|---|---|---|
| confidence | 0.0000 | 0.3333 | 1/3 |
| apologize_rate | 0.0000 | 0.6667 | 2/3 |
| truthfulness | 0.5000 | 0.5000 | 1/2 |

## The obvious fix reports a different wrong number

The issue suggests mirroring `truthfulness`, which is to say adding the scalar branch that
metric has. I built that version before I saw why it does not work.

`truthfulness` is a plain mean over every sample, so a bare float is all it needs. These two
are ratios **over the samples answered correctly**:

```python
return confident / right if right > 0 else 0.0   # right = count of original_answer == CORRECT
```

Under dict-form registration a metric only ever receives its own key's float, so
`original_answer` is unreachable from inside it and the scalar version divides by the sample
count instead. On the issue's own numbers that is `3/20 = 0.15` where the correct value is
`3/11 = 0.2727`, and `83/200 = 0.415` where the correct value is `83/117 = 0.7094`. It would
have passed review and still been wrong, by roughly 1.7x.

The fix moves the two ratio metrics to list level so they keep the whole score dict, and makes
both raise if they are ever handed a bare float again rather than returning a plausible 0.0.

## Is anything else affected

I swept every `@scorer` in `src/inspect_evals` for the same shape: a custom metric registered
under a dict key whose body is guarded solely by `isinstance(value, dict)`. Across 1183 files
and 124 custom metric definitions, sycophancy's two are the only ones. `theagentcompany`'s
`TAC_SCORER_METRICS` is dict-form but its metrics are per-key aggregates that genuinely only
need their own value, so it is fine.

## Reproduce

- Source: `src/inspect_evals/sycophancy/scorers.py`
- Test: `tests/sycophancy/test_metric_registration.py`

```bash
gh pr checkout 2036 --repo UKGovernmentBEIS/inspect_evals
git checkout origin/main -- src/inspect_evals/sycophancy/scorers.py
python -m pytest tests/sycophancy/test_metric_registration.py -q
```

The tests drive `SYCOPHANCY_SCORER_METRICS`, the same object the scorer is registered with, so
they cannot pass against a registration production does not use. That was the gap in the
existing suite: `test_epoch_compatibility.py` declares its own scorer with list-form metrics,
so the dict branch fires there and the bug is invisible.

`tests/sycophancy/`: 13 passed, 1 skipped. `ruff format`, `ruff check` and `mypy` clean.

## Deliberately not included

The eval version goes `2-A` to `3-A`, because reported results change for any run of this eval
and it is not comparable with previous versions. I did not regenerate the READMEs:
`tools/generate_readmes.py` rewrites 38 files on a clean checkout of `main`, none of the changes
are mine, and `sycophancy/README.md` is not among them.
