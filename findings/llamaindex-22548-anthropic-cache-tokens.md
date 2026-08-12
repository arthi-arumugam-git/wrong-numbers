# 3 prompt tokens reported for a call that billed 21,503

**Library:** run-llama/llama_index ·
**PR:** [#22548](https://github.com/run-llama/llama_index/pull/22548)
· **Status:** closed unmerged 

The third framework to make this mistake. See `pipecat#5163` (merged) and
`livekit/agents#6663` (merged) for the other two.

## What's wrong

Anthropic reports `input_tokens` **net of the prompt cache**, with the cached tokens in
`cache_read_input_tokens` and `cache_creation_input_tokens`. `get_tokens_from_response`
reads `input_tokens` alone:

```python
possible_input_keys = ("prompt_tokens", "input_tokens", "prompt_token_count")
for input_key in possible_input_keys:
    if input_key in usage:
        prompt_tokens = usage[input_key]
        break
```

Every token served from cache is dropped. And `input_tokens` is precisely the part that
was **not** cached, so the warmer the cache the worse the number gets:

```
input_tokens                   3
cache_read_input_tokens        20000
cache_creation_input_tokens    1500

reported prompt tokens         3
actually billed                21503
```

## Why it is worse than a wrong number

`TokenCountingHandler` is what LlamaIndex's cost analysis guide is built on, so this
under-reports spend by the whole cached portion of every prompt. Prompt caching pays off
on large stable system prompts, which is exactly when the dropped figure is biggest.

The same count feeds `token_budget`, which raises `ValueError` when exceeded. Computed
from a number that omits cache reads, **a budget silently fails to fire**. The guard that
exists to raise is the thing being fooled.

## The streaming path threw the evidence away

`llama-index-llms-anthropic` built its usage blob as:

```python
usage_metadata = {
    "input_tokens": r.message.usage.input_tokens,
    "output_tokens": r.message.usage.output_tokens,
}
```

The cache fields were discarded at the source, so nothing downstream could recover them
even in principle. Four sites, sync and async.

## The obvious fix double-counts

"Add any cache count you find" is wrong. OpenAI's `prompt_tokens` already includes
`prompt_tokens_details.cached_tokens`, and Gemini's `prompt_token_count` already includes
`cached_content_token_count`. Only the Anthropic-shaped keys can be summed.

`or 0` rather than a default in `.get`, because Anthropic may send the keys explicitly set
to `null` rather than omitting them, and `None` would propagate into the sum.

## Reproduce

Against released `llama-index-core 0.14.23`, no checkout needed:

```python
from types import SimpleNamespace
from llama_index.core.callbacks.token_counting import get_tokens_from_response

usage = {"input_tokens": 3, "output_tokens": 120,
         "cache_read_input_tokens": 20000, "cache_creation_input_tokens": 1500}
print(get_tokens_from_response(
    SimpleNamespace(raw={"usage": usage}, additional_kwargs={})))
# (3, 120)   <- 3, against 21503 actually billed
```

Seven tests in `llama-index-core/tests/callbacks/test_token_counter_cache_tokens.py`.
Three fail on `main`. Four pass on both: the uncached case, null cache fields, and two
boundary tests pinning OpenAI and Gemini as unchanged.

## Correction, 2026-08-12: the diagnosis was right and the fix was wrong

An adversarial re-audit found that **the patch proposed here would have double-counted, by
exactly 2x**, on the path it was most likely to run on.

The fix adds the cache counters unconditionally after selecting a prompt count, guarding on
**key spelling** rather than on whether the count is net or gross:

```python
prompt_tokens += sum(usage.get(k) or 0
    for k in ("cache_read_input_tokens", "cache_creation_input_tokens"))
```

LiteLLM's Anthropic path emits both shapes at once. `calculate_usage` adds the cache counters
into `prompt_tokens`, making it **gross**, and then passes the raw Anthropic-spelled keys
through as extra fields, which survive because `openai.types.CompletionUsage` is configured
`extra='allow'`. So the loop picks the already-gross `prompt_tokens` and the patch adds the
cached tokens a second time: 21,503 billed becomes 43,003 reported.

The pull request argued the opposite, that the fix was "deliberately narrow", and shipped two
boundary tests. Both test provider-native shapes. The one shape carrying a gross prompt count
**and** Anthropic-spelled keys is the one shape it never tested.

It was closed for an unrelated reason, so the bug never shipped. Nobody caught it, including
me, until this audit. It is kept here because a repository about numbers that come out wrong
while nothing raises has no business hiding one of its own.

The underlying defect is still real: `input_tokens` alone drops every cached token. The correct
fix normalises **before** summing, or sums only when no total is present, which is what
[`mcp-use#2127`](mcp-use-2127-streamed-usage-erased.md) does.