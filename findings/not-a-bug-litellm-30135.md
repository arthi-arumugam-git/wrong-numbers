# Not a bug: LiteLLM #30135

**Library:** BerriAI/litellm · **Issue:** [#30135](https://github.com/BerriAI/litellm/issues/30135)
· **Outcome:** investigated, reproduced, **not filed**

This one is in the collection because it's the counter-example. If the claim is "every library I
checked had a wrong number," the fair objection is that I went looking for wrongness. Here is the
case where the evidence looked exactly as damning and the number was correct.

## What was reported

`*_above_200k_tokens` rates configured via `model_info` are ignored and the base rate is applied
flat. A good report: specific, with spend-log evidence.

It looked identical to the Phoenix finding, which had just been confirmed. Filing it would have
been easy.

## What actually happens

Reproducing the reporter's exact config through the full Router → logging path:

```
response_cost = 7.3211525
```

Flat base-rate would have been `3.66036875`. **The tiered rates are carried through and applied.**

## Why the reporter's evidence reproduces anyway

The evidence is real. The above-200k fields genuinely do show as `null` in the stored
`model_map_information`. It just doesn't mean what it looks like it means: two different lookups
resolve two different ways:

- `_response_cost_calculator` resolves pricing **through the deployment**, carrying
  `router_model_id`. Per-deployment pricing survives. The cost is right.
- `get_model_cost_information`, which builds the spend-log map, calls
  `litellm.get_model_info(model=model_cost_name, custom_llm_provider=...)`, a **name-based lookup
  on the shared `{provider}/{model}` key**, which by design doesn't carry per-deployment pricing.

So the cost is correct and the logged map is misleading. A logging artifact, not a billing defect.

## The other half of the gap

The rest of the discrepancy was the reporter's expected figure, which assumed **graduated,
income-tax-style** pricing, each slice billed at its own rate. These providers don't work that
way; they switch the whole request to the higher rate.

Chasing that assumption down is what surfaced a real defect somewhere else entirely: LiteLLM's own
DashScope calculator *does* apply graduated slicing, and Alibaba Model Studio doesn't bill that
way. See [litellm #34760](litellm-34760-dashscope-tiers.md).

## Why this matters more than the twelve

Anyone can send pull requests. The judgement in a set like this isn't in the ones you file, it's in
the one you don't: the one where the evidence is convincing, the pattern matches something you
just confirmed elsewhere, and you go and check anyway.

Verify before you assert, including against yourself.

## Caveat on verification

The reproduction figure above is my own run, not something a reader can verify from a public
artifact. If that matters to you, ask and I'll post the script rather than restate the number.
