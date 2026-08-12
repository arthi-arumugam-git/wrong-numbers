# Higher pricing tiers unreachable on 24 endpoints

**Library:** Helicone/helicone · **PR:** [#5737](https://github.com/Helicone/helicone/pull/5737)
· **Status:** open · Fixes [#5690](https://github.com/Helicone/helicone/issues/5690)

This is the finding the whole write-up is built around.

## What's wrong

`getThresholdValueFunction` decides what number to compare against a model's pricing tier
thresholds:

```ts
switch (provider) {
  case "vertex": ...
  case "google-ai-studio": ...
  case "anthropic": ...
  case "xai": ...
  default: return () => 0;
}
```

`getPricingTier` picks the highest tier whose `threshold` is `<=` the value it's given. A constant
`0` always selects the cheapest tier, so every higher tier on every unhandled provider is
unreachable.

## The number

`gpt-5.4` on `openai` at 300,000 input / 50,000 output:

| | input | output | total |
|---|---|---|---|
| charged (base tier) | 300000 × $2.50/M = $0.75 | 50000 × $15/M = $0.75 | **$1.50** |
| correct (>272K tier) | 300000 × $5/M = $1.50 | 50000 × $22.50/M = $1.125 | **$2.625** |

**43% under**, on exactly the requests that cost the most.

## Sizing it

Scanning every endpoint config in `packages/cost/models/authors/` for `pricing.length > 1`:

```
handled     anthropic 3, google-ai-studio 3, vertex 7, xai 3
unreachable azure 2, bedrock 3, helicone 10, openai 2, openrouter 7
```

40 multi-tier endpoints, **24 on a provider the switch never handled**. Bedrock is in that list
and the filed issue didn't mention it: the three `claude-sonnet-4*` Bedrock endpoints each declare
a 200000 tier that was never selected.

## The obvious fix is wrong in the same way

The issue proposed adding four provider cases returning `input + cachedInput`. That fixes the
reported symptom, passes review, and **leaves Bedrock broken**, because Anthropic bills cache
writes as part of the prompt, which is exactly why the existing `anthropic` case adds `write5m`
and `write1h`.

The threshold basis keys off the model's **author**, not the serving provider. So the `default`
branch checks `author` and applies the Anthropic rule wherever an Anthropic-authored model is
served from, which also fixes Claude resold through OpenRouter and Helicone.

Get that backwards and you ship a fix that is silently wrong in the same way the original was.

## Reproduce

- Source: `packages/cost/models/calculate-cost.ts`
- Test: `packages/__tests__/cost/modelCostFromRegistry.test.ts`, 9 cases added to the
  `threshold-based pricing` block

```bash
gh pr checkout 5737 --repo Helicone/helicone
git checkout origin/main -- packages/cost/models/calculate-cost.ts
npx jest __tests__/cost/modelCostFromRegistry.test.ts
```

Observed on `main` with the tests applied:

```
● threshold-based pricing › should use higher tier pricing for OpenAI GPT-5.4 over 272K tokens
  Expected: 1.5
  Received: 0.75
```

Single-tier models are unaffected: their only tier has `threshold: 0`, so any value selects it.
The four existing provider cases are untouched, `vertex` in particular, which tiers
`cachedInputCost` off the cached-token count alone rather than the prompt.

**Credit:** issue [#5690](https://github.com/Helicone/helicone/issues/5690) was filed by
[@Anuj7411](https://github.com/Anuj7411). I wrote the fix, not the report.
