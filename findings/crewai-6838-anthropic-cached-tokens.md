# CrewAI reports 150 tokens for a call that billed 350

`crewAIInc/crewAI` · [#6838](https://github.com/crewAIInc/crewAI/pull/6838) ·
`lib/crewai/src/crewai/llms/providers/anthropic/completion.py`

## The number

A call with 200 cached input tokens, 50 fresh input tokens and 100 output tokens:

| | reported | billed |
|---|---|---|
| `total_tokens` | 150 | 350 |

A second reading makes it self-evident. On that same call `cached_prompt_tokens` comes back
as **200** while `prompt_tokens` is **50**, so the cached subset is larger than the set it
belongs to.

## The code

`_extract_anthropic_token_usage` reads both cache counters, surfaces them under their own
keys, and then builds the total without them:

```python
input_tokens = getattr(usage, "input_tokens", 0)
output_tokens = getattr(usage, "output_tokens", 0)
cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
cache_creation_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0
result = {
    "input_tokens": input_tokens,
    "output_tokens": output_tokens,
    "total_tokens": input_tokens + output_tokens,
    "cached_prompt_tokens": cache_read_tokens,
    "cache_creation_tokens": cache_creation_tokens,
}
```

Anthropic reports `input_tokens` net of the prompt cache and bills the two cache counters on
top of it. It never sends a total, so this one has to be constructed, and it was constructed
from the wrong two numbers.

## Why it is a cross-provider inconsistency, not a missing addition

Every other provider in the same codebase reports a prompt count that already contains its
cached portion. OpenAI nests `cached_tokens` inside `prompt_tokens`. Gemini uses
`total_token_count` and Bedrock uses the API's own total. Anthropic is the only one where the
cached tokens sit outside the value that gets mapped onto `prompt_tokens`.

`UsageMetrics.from_provider_dict` states the invariant this breaks, in its own docstring:

> Mirrors `BaseLLM._track_token_usage_internal` so per-LLM totals, flow-level aggregation, and
> OTel spans agree on every provider.

They do not agree. The same billed work through the Anthropic path and the OpenAI path
produces 150 and 350.

## The fix

Normalise to the OpenAI-compatible shape at extraction: `prompt_tokens` becomes the full
billed input, and `cached_prompt_tokens` stays a subset of it rather than a disjoint number a
consumer might add on top. It then flows unchanged through `UsageMetrics`,
`CrewOutput.token_usage` and the OTel span.

## Test

Eight, in `tests/llms/anthropic/test_anthropic_cached_token_totals.py`, four of which fail
before the change. One asserts parity directly: identical billed work described in Anthropic's
shape and OpenAI's shape must produce identical `UsageMetrics`.

## Why this one matters to the argument

It is the sixth independent framework carrying the same defect, after Pipecat, LiveKit,
LlamaIndex, Haystack and mcp-use. Three of those fixes are merged.
