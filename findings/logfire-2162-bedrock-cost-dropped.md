# `AnthropicBedrock` calls carry tokens but never a cost

**Library:** pydantic/logfire · **PR:** [#2162](https://github.com/pydantic/logfire/pull/2162)
· **Status:** open, unreviewed by a human maintainer as of 2026-08-02

## What's wrong

`get_anthropic_usage_attributes` hardcodes `provider_id='anthropic'`. Through Bedrock the model
ID is a Bedrock one, so the lookup is for `anthropic.claude-3-haiku-20240307-v1:0` inside the
`anthropic` provider, which has no such model. `calc_price` raises `LookupError`, the
`except Exception: pass` in `get_usage_attributes` swallows it, and the cost is dropped.

Tokens are set before that block, which is why they still show up and the failure reads as
"prices missing for Bedrock" rather than as an error.

## The number

Every `AnthropicBedrock` call, on every span. The prices are not missing. genai-prices resolves
all of these under `aws` today:

```
anthropic.claude-3-haiku-20240307-v1:0                        -> $0.00000425
us.anthropic.claude-3-7-sonnet-20250219-v1:0                  -> $0.000051
eu.anthropic.claude-3-7-sonnet-20250219-v1:0                  -> $0.000051
arn:aws:bedrock:eu-west-1:...:inference-profile/eu.anthropic. -> $0.000051
```

## Why the obvious fix fails, differently

Flipping `provider_id` to `'aws'` was my first patch. It raises:

```
ValueError: Missing value at `usage.inputTokens`
```

genai-prices' `aws` extractor expects the Bedrock Converse response shape, `usage.inputTokens`.
`AnthropicBedrock` is not the Converse API; it returns the Anthropic Messages shape,
`usage.input_tokens`. So `extract_usage` can read the body or the `aws` prices, but not both.

The fix stops going through `extract_usage` for this case. `input_tokens` and `output_tokens`
are already computed from the response two lines earlier, so `get_usage_attributes` takes an
optional `model_ref` plus the cache token split and prices those directly, bypassing the
body-shape step.

## Why the model ID and not the client type

`instrument_anthropic` knows whether it was handed a Bedrock client, but that does not reach
here. Streaming arrives via `AnthropicMessageStreamState.get_attributes`, which calls
`get_anthropic_usage_attributes` with an accumulated message and no client, so threading the
client through would mean changing the shared `instrument_llm_provider` signature and carrying
it into `StreamState` too. Matching the model ID covers both paths with one branch and fails
safe: a native Anthropic model name cannot take the `[region.]anthropic.` or `arn:aws:bedrock:`
shape, so anything that does not match falls through to the `anthropic` provider exactly as it
does today.

## Why the existing tests passed

`tests/otel_integrations/test_anthropic_bedrock.py` had **zero** `operation.cost` assertions,
against 27 in `test_anthropic.py`. The repo's own snapshot for the Bedrock path encoded the
missing cost as expected output, so the suite could not have caught this.

## Reproduce

- Source: `logfire/_internal/integrations/llm_providers/anthropic.py`, `.../usage.py`
- Test: `tests/otel_integrations/test_anthropic_bedrock.py`

```bash
gh pr checkout 2162 --repo pydantic/logfire
git checkout origin/main -- logfire/_internal/integrations/llm_providers/
python -m pytest tests/otel_integrations/test_anthropic_bedrock.py -q
```

The new parametrized test covers the plain model ID, the `us.` and `eu.` cross-region inference
profiles and the full inference-profile ARN.

```
tests/otel_integrations/test_anthropic_bedrock.py  6 passed
test_openai.py + test_llm_usage_attributes.py + test_anthropic_bedrock.py  86 passed
```

15/15 CI checks green. Both AI reviewers on the PR caught that the scope-prefix regex missed
`global.` and `us-gov.`, which is the same silent drop this exists to remove; `global.` prices
to its own cheaper entry, $0.018 against $0.0198 per 1M/1M. Fixed and credited in-thread.

## Scope

This is the `anthropic` SDK path. The reporter on
[logfire#1023](https://github.com/pydantic/logfire/issues/1023) is using pydantic-ai's
`BedrockConverseModel`, where the cost is recorded by pydantic-ai rather than here, so that half
is not addressed by this and I did not want to claim otherwise.

`test_anthropic.py::test_async_beta_messages` fails on a clean checkout of `main` here, before
any of this, so I left it alone.
