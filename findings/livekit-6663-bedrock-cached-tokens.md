# `CompletionUsage` contradicted its own documented contract on Bedrock

**Library:** livekit/agents · **PR:** [#6663](https://github.com/livekit/agents/pull/6663)
· **Status:** **merged 2026-08-02**, approved and merged by LiveKit's co-founder

## What's wrong

`CompletionUsage` documents two things about itself:

- `prompt_tokens` is "the number of input tokens used (includes cached tokens)"
- `total_tokens` is "completion + prompt tokens"

The AWS plugin met neither. Bedrock reports `inputTokens` already **net** of the cache and
puts the cached tokens in separate fields, so assigning it straight through drops them:

```python
prompt_tokens = usage["inputTokens"]
```

Two consequences, both silent. `prompt_tokens` excludes cached tokens, contradicting its own
docstring. And `total_tokens` was taken from the provider's `totalTokens`, which is computed
on a different basis, so the object could report a total that is not its own prompt plus its
own completion.

## Why it matters here specifically

This is a voice-agent framework. The system prompt and the conversation history are re-read
from the prompt cache on every turn, so within a few turns cache reads are most of the input.
A turn billed for 2100 input tokens with 2000 of them cached reported **150**.

Anyone billing from `prompt_tokens`, or reconciling against an AWS invoice, was reading a
number that got further from the truth the longer the conversation went on.

## The tell

LiveKit's **own** Anthropic plugin already did it correctly, for the same models served
directly rather than through Bedrock:

```python
prompt_token = self._input_tokens + self._cache_creation_tokens + self._cache_read_tokens
```

So one `CompletionUsage` disagreed with another depending only on which provider filled it.
The correct arithmetic was already in the repository.

## The fix

```python
cache_read_tokens = usage.get("cacheReadInputTokens") or 0
cache_creation_tokens = usage.get("cacheWriteInputTokens") or 0
prompt_tokens = usage["inputTokens"] + cache_read_tokens + cache_creation_tokens
```

`or 0` rather than a default in `.get`, because Bedrock may send the keys explicitly set to
`null` rather than omitting them, and `None` would propagate into the sum.

`total_tokens` is now computed as prompt plus completion rather than taken from the provider,
so the object satisfies its own documented definition.

## Reproduce

- Source: `livekit-plugins/livekit-plugins-aws/livekit/plugins/aws/llm.py`
- Test: `livekit-plugins/livekit-plugins-aws/tests/test_llm_usage_cached_tokens.py`

Five tests. Four fail on `main`:

```bash
gh pr checkout 6663 --repo livekit/agents
cd livekit-plugins/livekit-plugins-aws
pytest tests/test_llm_usage_cached_tokens.py -q          # 5 passed
git checkout origin/main -- livekit/plugins/aws/llm.py
pytest tests/test_llm_usage_cached_tokens.py -q          # 4 failed
```

The one that passes on both is the uncached case: with no cache in play the previous
arithmetic was already right, which is exactly why nothing raised.

## Same defect, one framework over

`pipecat#5163` at Daily was the identical mistake in the identical place: the Anthropic and
Bedrock services computed prompt plus completion against an input count already net of the
cache. Two independent implementations of the same idea, the same arithmetic error. See
[`../README.md`](../README.md).
