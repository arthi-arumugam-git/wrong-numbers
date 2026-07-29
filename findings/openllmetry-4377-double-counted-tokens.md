# Streamed output tokens double-counted

**Library:** traceloop/openllmetry · **PR:** [#4377](https://github.com/traceloop/openllmetry/pull/4377)
· **Status:** open, unreviewed as of 2026-07-29

## What's wrong

`_process_response_item` treats `message_delta.usage.output_tokens` as an increment and adds it to
the count already stored from `message_start`:

```python
item_output_tokens = dict(item.usage).get("output_tokens", 0)
existing_output_tokens = complete_response["usage"].get("output_tokens", 0)
complete_response["usage"]["output_tokens"] = (
    item_output_tokens + existing_output_tokens
)
```

Anthropic sends `message_delta.usage.output_tokens` as the **running total for the whole
message**. The value in `message_start` is a partial count already contained in it. Adding them
inflates output tokens, and therefore total tokens and any cost computed downstream, on every
streamed Anthropic span.

The vendor SDK assigns rather than adds, in `anthropic/lib/streaming/_messages.py`:

```python
current_snapshot.usage.output_tokens = event.usage.output_tokens
```

This repo's own Bedrock streaming wrapper also overwrites rather than accumulates.

## The number

Replaying the SSE events from the repo's existing cassette
(`tests/cassettes/test_messages/test_anthropic_message_streaming_legacy.yaml`) through both
accumulators:

```
message_start.usage : {'input_tokens': 17, 'output_tokens': 3}
message_delta.usage : {'output_tokens': 171}

openllmetry  output_tokens : 174
anthropic SDK output_tokens: 171   <- ground truth
```

A 1.75% overcount on this recording. The gap is whatever `message_start` reported, so it grows
with prompt-cache and tool-use shapes where that initial count is larger.

## Why it survived CI

`test_anthropic_message_streaming_legacy` already asserted `input_tokens == 17` **and** the
`input + output == total` identity. It never asserted the output value itself, the one that was
wrong, so the bug passed CI for as long as it existed.

That is the cleanest example in the whole set of why these survive: the test suite was not thin,
it was thin in exactly one place.

## Reproduce

- Source: `packages/opentelemetry-instrumentation-anthropic/opentelemetry/instrumentation/anthropic/streaming.py`
- Test: `packages/opentelemetry-instrumentation-anthropic/tests/test_messages.py`

```bash
gh pr checkout 4377 --repo traceloop/openllmetry
git checkout origin/main -- packages/opentelemetry-instrumentation-anthropic/opentelemetry/instrumentation/anthropic/streaming.py
python -m pytest packages/opentelemetry-instrumentation-anthropic/tests/test_messages.py -k streaming_legacy -q
```

Fails with `assert 174 == 171`. Replays a recorded cassette: no network or API key.
