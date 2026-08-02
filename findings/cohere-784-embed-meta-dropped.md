# Batched embed drops `meta.tokens` and image billed units

**Library:** cohere-ai/cohere-python · **PR:** [#784](https://github.com/cohere-ai/cohere-python/pull/784)
· **Status:** open, unreviewed by a human maintainer as of 2026-08-02

## What's wrong

`Client.embed()` goes through `merge_embed_responses` on every call unless you pass
`batching=False` or pass images. That path rebuilds `ApiMeta` from scratch inside
`merge_meta_field`, setting `api_version`, four of the six `ApiMetaBilledUnits` fields, and
`warnings`.

Everything else is dropped on the floor: `meta.tokens`, `meta.cached_tokens`,
`billed_units.images`, `billed_units.image_tokens`.

Since `batching` defaults to `True`, **the default path is the lossy one**.

## The number

```python
co.embed(texts=texts).meta.tokens                  # None
co.embed(texts=texts, batching=False).meta.tokens  # populated
```

Same request, different metadata. Nothing in the signature suggests a batching flag should change
which usage numbers come back. Anyone reading `meta.tokens` for accounting gets `None` and no
error explaining why.

## Why it happened, and how it's stopped from happening again

`merge_meta_field` lists the fields it copies **by hand**. `images`, `image_tokens`, `tokens` and
`cached_tokens` were added to the models and the merge was never updated, and nothing failed. The
same thing will happen to the next field added.

So one of the three tests drives its assertions off the model fields rather than a hardcoded list:

```python
billed_fields = get_fields(ApiMetaBilledUnits())
...
for field in billed_fields:
    self.assertEqual(getattr(merged.billed_units, field), 2, f"billed_units.{field} was dropped")
```

Add a field to `ApiMetaBilledUnits` or `ApiMetaTokens` without touching `merge_meta_field` and
that test fails immediately.

## One deliberate choice

`tokens` stays `None` when none of the input metas carried it, rather than building an
`ApiMetaTokens(None, None)`. A merged response with no token counts then looks exactly as it does
today, which is why the existing equality assertions in `test_embed_utils.py` needed no change.

## Reproduce

- Source: `src/cohere/utils.py`
- Test: `tests/test_embed_utils.py`, 3 cases

```bash
gh pr checkout 784 --repo cohere-ai/cohere-python
git checkout origin/main -- src/cohere/utils.py
python -m pytest tests/test_embed_utils.py -q
```
