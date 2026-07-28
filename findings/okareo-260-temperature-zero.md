# `temperature=0` overwritten by the class default

**Library:** okareo-ai/okareo-python-sdk · **PR:** [#260](https://github.com/okareo-ai/okareo-python-sdk/pull/260)
· **Status:** open, unreviewed as of 2026-07-28

## What's wrong

`Driver._get_driver_fields` guards every field assignment with a truthiness check:

```python
if response.temperature:
    self.temperature = response.temperature
```

`DriverModelResponse.temperature` and `VoiceDriverModelResponse.temperature` are declared as
**required `float`**. So this guard never protects against a missing value. The only value it can
ever filter out is a legitimate `0`.

## The number

```python
driver = okareo.create_or_update_driver(Driver(name="deterministic", temperature=0))
driver.temperature   # 0.6
```

`0` becomes `0.6`, the `Driver` class default. `get_driver_by_name` returns the same wrong value.

## Why it's worse than a bad read

`Driver.to_dict()` is exactly what `create_or_update_driver` posts back. So a get-then-save round
trip **silently rewrites the stored `0` to `0.6` on the server**, and a deterministic driver stops
being deterministic. Nothing raises and nothing is logged.

`run_simulation` hits this path too — it calls `create_or_update_driver(driver)` for an inline
`Driver`, so the returned object already carries the wrong temperature.

## Scope of the fix

Compare against `None` instead. `model_id` and `project_id` were deliberately left alone — those
are genuinely `Optional`/`Unset` on the response models, so a truthiness check there isn't hiding
anything.

## Reproduce

- Source: `src/okareo/model_under_test.py`
- Test: `okareo_tests/test_model_under_test.py`

```bash
gh pr checkout 260 --repo okareo-ai/okareo-python-sdk
git checkout origin/main -- src/okareo/model_under_test.py
pytest okareo_tests/test_model_under_test.py -k driver_from_response
```

The tests construct a `DriverModelResponse` directly — no network or API key.
