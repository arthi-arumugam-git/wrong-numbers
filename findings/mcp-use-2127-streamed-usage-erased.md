# mcp-use: the streamed total was not wrong, it was gone

[`mcp-use/mcp-use#2127`](https://github.com/mcp-use/mcp-use/pull/2127)

This is the fifth framework with the Anthropic cached-token defect, after Pipecat, LiveKit,
LlamaIndex and Haystack. It also has a second one I had not seen anywhere else, and that one
is worse.

## The shared defect

Anthropic reports `input_tokens` **net of the prompt cache**, and bills
`cache_read_input_tokens` and `cache_creation_input_tokens` separately on top. It never sends
`total_tokens`, so the computed branch is always the one that runs:

```ts
const totalTokens =
  numberAt(usage, "totalTokens", "total_tokens", "totalTokenCount") ??
  (inputTokens !== undefined && outputTokens !== undefined
    ? inputTokens + outputTokens
    : undefined);
```

A call billed on 21,623 tokens reports 123. `cache_creation_input_tokens` appeared **nowhere
in the repository**, and Anthropic bills cache writes above the base rate, so cache writes
were invisible rather than merely undercounted.

## The variant specific to streaming

`tokenUsageFromRecord` returns every key and sets the ones it did not find to `undefined`:

```ts
return { inputTokens, outputTokens, totalTokens, cachedInputTokens, reasoningTokens };
```

Anthropic's streaming `message_delta` carries `output_tokens` and nothing else. The merge was
a spread:

```ts
usage = { ...usage, ...deltaUsage };
```

Because the absent keys **exist** on `deltaUsage` with the value `undefined`, the spread
overwrites the counters captured at `message_start` rather than leaving them alone:

```
after message_start : {"inputTokens":3,"outputTokens":1,"totalTokens":4,"cachedInputTokens":20000}
after message_delta : {"outputTokens":500}
```

After any streamed call the entire input side of the accounting was gone. An end-to-end test
driving the real SSE sequence through `streamChat` reports, on the base commit:

```
- Expected  "totalTokens": 21623
+ Received  "totalTokens": undefined
```

Not a wrong number. An absent one, with nothing raised.

## What the review found that I had not

Their AI reviewer asked for an end-to-end test rather than one exercising the merge helper in
isolation. Writing it surfaced a **third** copy of the same arithmetic, in `message_stop`,
which recomputed the total as `inputTokens + outputTokens`. My fix had survived it only
because `??` short-circuited on a value already set. That is luck, not design, and two places
knowing how a provider bills is precisely how this drifts back. One place owns it now.

The same pass found `InspectorTokenUsage` declaring `cachedInputTokens` and `reasoningTokens`,
the trace view reading them, and the parser never populating either, so both had always
rendered as absent whatever the provider sent.

## The boundary, which is the part worth pinning

The obvious fix is to add `cachedInputTokens` to the computed total. That is right for
Anthropic and **wrong for OpenAI**, whose `cached_tokens` sits *inside* `prompt_tokens`, so
adding it double counts. Once usage has been normalised the distinction is gone, which is why
only the Anthropic-shaped keys are summed, why `mergeTokenUsage` deliberately does not touch
the total at all, and why there is a test pinning the OpenAI case at 14.
