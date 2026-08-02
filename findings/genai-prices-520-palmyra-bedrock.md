# Writer Palmyra X4 and X5 on Bedrock resolve no price at all

**Library:** pydantic/genai-prices · **PR:** [#520](https://github.com/pydantic/genai-prices/pull/520)
· **Status:** open, unreviewed by a human maintainer as of 2026-08-02

## What's wrong

`us.writer.palmyra-x4-v1:0` and `us.writer.palmyra-x5-v1:0` resolve no price. The `aws` provider
has no `writer.*` entries at all, so `find_model` returns `None` and `calc_price` raises
`LookupError`.

Both are real Bedrock model references. pydantic-ai lists them in `BedrockModelName` and ships a
recorded cassette for `us.writer.palmyra-x4-v1:0`, so the cost path is reached with exactly these
strings in the wild. pydantic-ai's instrumentation catches the `LookupError` and skips setting
`operation.cost`, so the span carries token counts with an empty cost column and nothing surfaces
to say why.

## The number

Two real models, priced at nothing. On genai-prices 0.0.72, for 1000 input and 500 output tokens:

```
before:
us.writer.palmyra-x4-v1:0  -> LookupError: Unable to find model with model_ref=... in aws
us.writer.palmyra-x5-v1:0  -> LookupError: Unable to find model with model_ref=... in aws

after:
us.writer.palmyra-x4-v1:0  -> writer.palmyra-x4-v1:0  total=$0.0075
us.writer.palmyra-x5-v1:0  -> writer.palmyra-x5-v1:0  total=$0.0036
```

## The change

Two model entries in `prices/providers/aws.yml`, plus the regenerated data files. Prices from
[AWS Bedrock pricing](https://aws.amazon.com/bedrock/pricing/), checked 2026-07-29:

| model | input /Mtok | output /Mtok |
| --- | --- | --- |
| Palmyra X4 | $2.50 | $10.00 |
| Palmyra X5 | $0.60 | $6.00 |

Bedrock serves both through cross-region inference profiles, so the model reference arrives
prefixed. Matching is on `contains: writer.palmyra-x4` and `writer.palmyra-x5`, the pattern the
rest of the file already uses for prefixed Bedrock references, which covers the bare form, the
`us.` / `eu.` / `apac.` forms and the inference-profile ARN alike. AWS publishes a single flat
price for these two, so there is no regional variant to model.

## Reproduce

- Source: `prices/providers/aws.yml`
- Test: `tests/test_model_matching.py`

```bash
gh pr checkout 520 --repo pydantic/genai-prices
git checkout origin/main -- prices/ packages/
python -m pytest tests/test_model_matching.py -q
```

Four cases, the bare and the `us.` prefixed reference for each model. They fail on `main` with
`assert None is not None`. Full suite: 683 passed, 41 xfailed. `tests/dataset/extract_usages.py`
reports `usages.json` up to date; ruff format and check clean.

## Deliberately not included

Other Bedrock references pydantic-ai advertises still resolve nothing: `anthropic.claude-v2`,
`cohere.command-r-v1:0`, `meta.llama3-1-405b-instruct-v1:0` and a few more. Kept out so the price
sourcing in this one stays reviewable.

## Related

Reported against Logfire in [pydantic/logfire#1023](https://github.com/pydantic/logfire/issues/1023),
where Bedrock spans show tokens but no cost. This closes one concrete gap in that report. The
other half of it is [logfire#2162](logfire-2162-bedrock-cost-dropped.md).
