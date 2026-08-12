# The weights proxy wrapped an already-wrapped URL, and dropped the gateway's base path

**Library:** roboflow/inference · **Issue:** [#2662](https://github.com/roboflow/inference/issues/2662)
(filed by Roboflow) · **PR:** [#2748](https://github.com/roboflow/inference/pull/2748)
· **Status:** closed unmerged 

## What's wrong

Two functions implement the same `/proxy?url=` contract for a secure gateway.
`wrap_url` in `inference/core/utils/url_utils.py` handles server traffic.
`roboflow_secure_gateway_proxy_url_builder` in
`inference_models/inference_models/weights_providers/roboflow.py` handles weights traffic.
They had drifted apart in two ways.

**No idempotence guard.** `wrap_url` gained one in
[#2658](https://github.com/roboflow/inference/pull/2658), with a comment saying values may
already be wrapped and wrapping twice would proxy the proxy. The weights builder did not get
it. On `main`, wrapping an already-wrapped URL gives:

```
https://gw.local/proxy?url=https%3A%2F%2Fgw.local%2Fproxy%3Furl%3Dhttps%253A%252F%252Fapi.roboflow.com%252Fweights
```

**The gateway base path was dropped.** The builder took `urlsplit` scheme and netloc only:

```python
gateway_base = f"{parts.scheme}://{parts.netloc}"   # discards parts.path
```

`wrap_url` uses `SECURE_GATEWAY.rstrip("/")` and keeps it. So with
`SECURE_GATEWAY=https://gw.local/edge`, weights traffic goes to `gw.local/proxy` while server
traffic goes to `gw.local/edge/proxy`.

## The number

Neither failure raises. There is no wrong number to print here, which is the point: the
weights are simply fetched from somewhere other than the gateway you configured, and that is
the one thing a secure gateway exists to prevent. It fails silently in the direction of less
security rather than more.

## The two fixes interact

This is the part that is easy to get wrong. Once the base path is preserved, the idempotence
guard has to compare against a prefix that **includes** that path, or fixing the path
reintroduces double-wrapping under `/edge`. There is a test for that case on its own.

## Is anything else affected

The issue asked for either one shared implementation or behaviour-identical ones with
cross-package tests. Sharing would put a dependency between two packages that do not currently
have one, so this takes the second option.

The parity test lives in the `inference` unit suite rather than the `inference_models` one,
because `unit_tests_inference_x86.yml` already runs `pip install --no-deps ./inference_models`,
so both are importable there, whereas the `inference_models` suite runs with
`working-directory: inference_models`. It is guarded with `importorskip` regardless.

Part 2 of #2662, the per-run `step_execution_mode` bypass, is deliberately untouched. That one
needs gateway support in `inference_sdk`'s `InferenceHTTPClient` or a guard at the
`StepExecutionMode` consumption point, and it is a design decision rather than a divergence
between two functions.

## Reproduce

- Source: `inference_models/inference_models/weights_providers/roboflow.py`
- Tests: `inference_models/tests/unit_tests/weights_providers/test_roboflow.py` and
  `tests/inference/unit_tests/core/utils/test_url_utils.py`

```bash
git clone https://github.com/roboflow/inference.git && cd inference
python -m pytest inference_models/tests/unit_tests/weights_providers/test_roboflow.py \
  -k "idempotent or preserves_gateway_base_path" -q
PYTHONPATH=inference_models python -m pytest \
  tests/inference/unit_tests/core/utils/test_url_utils.py -q
```

Five tests fail before the change: four behaviour tests, plus a six-case parametrized
cross-package test asserting the two wrappers produce byte-identical output across six gateway
spellings and that both are idempotent. All six of those cases fail on `main`, including the
plain `gateway.local` one, because the idempotence half diverged for every spelling.
