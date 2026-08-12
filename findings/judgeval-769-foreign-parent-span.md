# A foreign global OTel span is adopted as parent

**Library:** JudgmentLabs/judgeval · **PR:** [#769](https://github.com/JudgmentLabs/judgeval/pull/769)
· **Status:** open 

## What's wrong

[#749](https://github.com/JudgmentLabs/judgeval/pull/749) made `get_current_context()` read the
**global** OTel context whenever this provider owns the global provider. That folded two different
jobs into one method:

- **write**: publish the active Judgment span into the global context, so third-party
  instrumentation calling `trace.get_current_span()` can see it
- **read**: decide what a newly started Judgment span should be parented to

Only the write direction actually needs to be global.

Reading parenting from the global context means whatever span a host application or unrelated
instrumentation happens to have left current becomes the parent of the next Judgment span, which
silently reroots it onto a foreign trace.

## What you see

Nothing errors. The trace simply shows up in the wrong tree, with the wrong `trace_id`.

For a tracing library specifically, this is the failure that is hardest to notice, because the
only artifact is a shape in a UI that looks like a shape.

## The change

- `get_current_context()` always reads Judgment's private runtime context. Parenting never
  consults the global context.
- `get_global_context()` added for the cases that genuinely want the global view.
- `attach_context()` attaches to the private context and, when we own the global provider, mirrors
  the same context into the global one. It returns both tokens in a `_ContextToken` so
  `detach_context()` unwinds both, global first.

The write path is unchanged in effect, so the interop #749 was after still works.

## History worth noting

This is the third pass at the same regression: fixed once in #749, back again in #751, and #752
had been open since 6 July aiming at it. This PR is an independent take with a failing test.

## Reproduce

- Source: `src/judgeval/trace/judgment_tracer_provider.py`
- Test: `src/tests/trace/test_tracer_provider.py`, class `TestForeignGlobalParent`

```bash
gh pr checkout 769 --repo JudgmentLabs/judgeval
git checkout origin/main -- src/judgeval/trace/judgment_tracer_provider.py
python -m pytest src/tests/trace/test_tracer_provider.py -k ForeignGlobalParent -q
```

Observed on `main`:

```
>       assert span.parent is None
E       assert SpanContext(trace_id=0x56a27dc4..., span_id=0x2832975e..., ...) is None
```
