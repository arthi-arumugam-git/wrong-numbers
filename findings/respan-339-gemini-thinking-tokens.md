# Gemini thinking tokens land on no attribute at all

**Library:** respanai/respan · **PR:** [#339](https://github.com/respanai/respan/pull/339)
· **Status:** open, unreviewed by a human maintainer as of 2026-08-02

## What's wrong

Gemini reports `thoughtsTokenCount` separately from `candidatesTokenCount`, and bills it at the
output rate.

`respan-instrumentation-google-adk` reads that field and folds it into the output count:

```ts
const thoughtsTokens = numberValue(firstDefined(usage?.thoughtsTokenCount, usage?.thoughts_token_count));
const normalizedOutputTokens = outputTokens === undefined ? undefined : outputTokens + (thoughtsTokens ?? 0);
```

Three other instrumentations in the same monorepo read only prompt, candidates and total, and
drop it: `respan-instrumentation-vertexai` (Python and JS) and
`respan-instrumentation-google-genai`.

So this is not a claim about what the right behaviour is. It is their behaviour, applied
inconsistently across four packages.

## The number

A Gemini 2.5 Flash call with thinking enabled returns `prompt=100, candidates=50, thoughts=800,
total=950`. The three packages above emit:

| attribute | emitted | correct |
|---|---|---|
| prompt tokens | 100 | 100 |
| completion tokens | **50** | **850** |
| total tokens | 950 | 950 |

Two things go wrong. The span contradicts itself on its face, because 100 + 50 is not 950. And
the 800 thinking tokens land on no attribute at all, so they are not merely mislabelled, they
are unrecoverable downstream. On 2.5 Pro, output bills at $10/1M against $1.25/1M for input, so
anything costing off these spans under-reports output by about 94% on that call.

## Why the existing tests passed

Every usage fixture in the three suites looks like this:

```python
def make_usage(prompt_tokens: int = 3, completion_tokens: int = 4) -> Obj:
    return Obj(
        prompt_token_count=prompt_tokens,
        candidates_token_count=completion_tokens,
        total_token_count=prompt_tokens + completion_tokens,
    )
```

No thoughts field, and `total` computed as `prompt + completion`. Under that fixture the identity
holds and the assertion passes whether or not the fold is present. The defect was invisible to
the suite by construction.

## Reproduce

- Source: `_translator.py` and `_translator.ts` in the three named packages
- Test: `tests/test_instrumentation.py` (Python), `tests/vertexai_instrumentor.test.mjs` (JS)

```bash
gh pr checkout 339 --repo respanai/respan
git checkout origin/main -- python-sdks/instrumentations/respan-instrumentation-vertexai/src/
python -m pytest python-sdks/instrumentations/respan-instrumentation-vertexai/tests/ -q
```

```
FAILED tests/test_instrumentation.py::test_thinking_tokens_fold_into_the_output_count
E   assert 50 == 850
```

Each package gets the thinking-enabled case plus two controls: no thoughts field at all, which
is every non-thinking model, and thoughts present but zero, which is thinking budget set to zero.
The controls are the point. They pass with and without the fix, which is what shows this does not
regress non-thinking models.

## Deliberately not included

Emitting thinking tokens as their own attribute is defensible, and `crewai` and `pydantic-ai` in
this repo already do something like it. That is a feature. This is a wrong number, so the scope
stays at six source files and 32 lines.
