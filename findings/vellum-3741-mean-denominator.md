# Mean metric divides by the unfiltered length

**Library:** vellum-ai/vellum-python-sdks · **PR:** [#3741](https://github.com/vellum-ai/vellum-python-sdks/pull/3741)
· **Status:** open 

## What's wrong

`VellumTestSuiteRunResults.get_mean_metric_output` filters `None` out of the numerator but divides
by the length of the **unfiltered** list:

```python
return sum(cast(Iterable[float], filter(lambda o: isinstance(o, float), output_values))) / len(output_values)
```

`get_numeric_metric_output_values` is declared `-> List[float | None]`, and
`TestSuiteRunMetricNumberOutput.value` is `Optional[float]`, so `None` is a legal and reachable
element, not a defensive case that never happens.

## The number

Executions scored `[1.0, None, 1.0, None]`:

- Before: **0.5**
- After: **1.0**

Any test suite run where some executions produced no score returns a mean that is silently too
low. No exception, no warning.

The all-`None` case is worse: it returned **0.0**, which reads as a real score of zero. It now
raises `TestSuiteRunResultsException` instead.

## Reproduce

- Source: `src/vellum/evaluations/resources.py`
- Test: `src/vellum/evaluations/tests/test_resources.py`

```bash
gh pr checkout 3741 --repo vellum-ai/vellum-python-sdks
git checkout origin/main -- src/vellum/evaluations/resources.py
python -m pytest src/vellum/evaluations/tests/test_resources.py -q
```

Fails on `main` with `assert 0.5 == 1.0`. `black`, `isort`, `flake8` and `mypy` clean on both
touched files.

## Deliberately not included

`get_min_metric_output` and `get_max_metric_output` use the same `isinstance(o, float)` filter,
and on an all-`None` set they leak a bare `ValueError: min() iterable argument is empty` rather
than `TestSuiteRunResultsException`. Left out to keep this to one change and one test.
