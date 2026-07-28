# `timeout` accepted and never passed to the client

**Library:** okareo-ai/okareo-python-sdk · **PR:** [#261](https://github.com/okareo-ai/okareo-python-sdk/pull/261)
· **Status:** open, unreviewed as of 2026-07-28

## What's wrong

`Okareo.__init__` takes a `timeout` argument and never uses it:

```python
def __init__(
    self, api_key: str, base_path: str = BASE_URL, timeout: float = HTTPX_TIME_OUT
):
    self.api_key = api_key
    self.client = Client(base_url=base_path, raise_on_unexpected_status=True)
```

## Why it's worse than a no-op

`Client._timeout` stays at its `None` default, so `get_httpx_client()` constructs
`httpx.Client(timeout=None)`.

Passing `None` explicitly is **not** the same as leaving it out — it disables httpx's own 5 second
default. The SDK therefore runs with `Timeout(timeout=None)`: no connect, read, write or pool
timeout at all. A connection that hangs hangs **forever** rather than raising.

So the parameter doesn't merely fail to apply the value you asked for; its absence removes a
default that would otherwise have protected you.

`HTTPX_TIME_OUT` is read in `src/okareo/common.py` and used only as the default value of that
unused parameter, so setting it does nothing either.

## Where it came from

A regression from `2eca8db` ("switch to openapi-python-client, rm pydantic dependency, move
pytest-httpx to dev deps"), which replaced

```python
self.httpx_handler = HTTPXHandler(
    api_key=self.api_key, base_path=base_path, timeout=timeout
)
```

with `self.client = Client(base_url=base_path)` and left `timeout` on the signature.

## Reproduce

- Source: `src/okareo/okareo.py`, `src/okareo/common.py`
- Test: `okareo_tests/test_client.py`

```bash
gh pr checkout 261 --repo okareo-ai/okareo-python-sdk
git checkout origin/main -- src/okareo/okareo.py src/okareo/common.py
pytest okareo_tests/test_client.py -q
```
