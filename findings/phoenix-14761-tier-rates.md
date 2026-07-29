# LiteLLM tier rates never reach the cost manifest

**Library:** Arize-ai/phoenix · **PR:** [#14761](https://github.com/Arize-ai/phoenix/pull/14761)
· **Status:** open, unreviewed as of 2026-07-29 · Closes [#14314](https://github.com/Arize-ai/phoenix/issues/14314)

## What's wrong

Phoenix builds its cost manifest from LiteLLM's pricing data via `sync_models.py`. That script
reads only the flat rate fields.

LiteLLM also publishes `input_cost_per_token_above_200k_tokens` and friends: whole-prompt tier
rates that **replace** the base rate outright once the prompt exceeds the threshold. The script
never matched them.

The shipped manifest carried **zero** `threshold_based` customizations across **267 models**.

## What makes this one interesting

Nobody wrote a bug. `ThresholdBasedTokenPriceCustomization` and `ThresholdBasedTokenCostCalculator`
both work correctly and are fully tested. They were simply never handed anything to do. The defect
lives entirely in the fact that one producer and one consumer never agreed on a field name.

## The number

Regenerating the manifest with tier extraction in place produces **77 customizations across 23
models**, up from zero.

| Model | Base input | Above threshold | Under-bill |
|---|---|---|---|
| `gemini-2.5-pro` | `1.25e-6` | `2.5e-6` (200K) | 2x |
| `claude-sonnet-4-5` | `3e-6` | `6e-6` (200K) | 2x |
| `gpt-5.4` | `2.5e-6` | `5e-6` (272K) | 2x |
| `gpt-5.5` | `5e-6` | `1e-5` (272K) | 2x |

Output rates too: `gpt-5.4` goes `1.5e-5` → `2.25e-5` above 272K.

## A design note

`extract_threshold_customization()` matches `<field>_above_<N>k_tokens` for each of the six priced
fields and emits a customization keyed on `llm.token_count.prompt`. The key is deliberate:
LiteLLM's breakpoints are a function of **prompt** length, so output and cache rates key off the
prompt count too, not their own token type.

Where a model publishes more than one tier the lowest threshold wins, which is where billing first
diverges from the base rate, and the script prints the tiers it didn't use rather than dropping
them silently.

## Reproduce

- Source: `.github/.scripts/sync_models.py`
- Generated: `src/phoenix/server/cost_tracking/model_cost_manifest.json`
- Test: `tests/unit/server/cost_tracking/test_sync_models_tier_rates.py`

```bash
gh pr checkout 14761 --repo Arize-ai/phoenix
git checkout origin/main -- .github/.scripts/sync_models.py
python -m pytest tests/unit/server/cost_tracking/test_sync_models_tier_rates.py -q
```

Note this PR also regenerates the manifest, which is a large generated diff. The test exercises
the extraction function directly rather than the committed manifest.

**Credit:** the issue this closes, [#14314](https://github.com/Arize-ai/phoenix/issues/14314), was
filed by [@Anuj7411](https://github.com/Anuj7411). I wrote the fix, not the report.
