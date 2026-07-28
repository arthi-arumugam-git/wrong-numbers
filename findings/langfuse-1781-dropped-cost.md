# Cost dropped when usage is a dict or cost is an int

**Library:** langfuse/langfuse-python · **PR:** [#1781](https://github.com/langfuse/langfuse-python/pull/1781)
· **Status:** open, unreviewed as of 2026-07-28

## What's wrong

`_parse_cost` in `langfuse/openai.py`:

```python
if hasattr(usage, "cost") and isinstance(getattr(usage, "cost"), float):
```

**1. `usage` as a dict.** `hasattr({"cost": 0.002}, "cost")` is `False`, so cost is dropped
entirely. Not hypothetical — `_parse_usage` directly above already branches on
`isinstance(usage, dict)`, and `_update_langfuse_generation` calls both with the same object:

```python
if usage is not None:
    update["usage_details"] = _parse_usage(usage)
    update["cost_details"] = _parse_cost(usage)
```

So any dict-shaped usage that `_parse_usage` handles correctly loses its cost.

**2. An integer cost.** `isinstance(0, float)` is `False` in Python. OpenRouter reports
`"cost": 0` for free models and for fully cached responses, and any whole-number cost serialises
as an int.

## The number

Only one of five realistic shapes survives:

| input | before | after |
|---|---|---|
| `Usage(cost=0.0021)` | `{"total": 0.0021}` | `{"total": 0.0021}` |
| `Usage(cost=0)` | `None` | `{"total": 0.0}` |
| `Usage(cost=2)` | `None` | `{"total": 2.0}` |
| `{"cost": 0.0021}` | `None` | `{"total": 0.0021}` |
| `{"cost": 0}` | `None` | `{"total": 0.0}` |

The invocation is recorded with no cost at all. It doesn't record a wrong cost — it records
nothing, which reads downstream as free.

## One detail worth keeping

`bool` is excluded explicitly, because it is a subclass of `int` — otherwise a stray
`"cost": true` would be recorded as a cost of `1.0`.

## Reproduce

- Source: `langfuse/openai.py`
- Test: `tests/unit/test_parse_cost.py`, 8 cases

```bash
gh pr checkout 1781 --repo langfuse/langfuse-python
git checkout origin/main -- langfuse/openai.py
python -m pytest tests/unit/test_parse_cost.py -q
```

Observed on `main`:

```
FAILED tests/unit/test_parse_cost.py::test_dict_with_float_cost
FAILED tests/unit/test_parse_cost.py::test_integer_cost_is_not_dropped
2 failed, 6 passed
```

The other six cover `None` usage, an object without `cost`, a dict without `cost`, and the bool
and string rejections — so the fix can't widen the accepted set by accident.
