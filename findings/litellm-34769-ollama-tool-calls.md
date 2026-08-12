# `ollama/` drops every tool call when `stream=true`

**Library:** BerriAI/litellm · **PR:** [#34769](https://github.com/BerriAI/litellm/pull/34769)
· **Status:** open · Automated review: 5/5
· Fixes [#19742](https://github.com/BerriAI/litellm/issues/19742)

Not a wrong number. The same silence, in control flow, and the most vivid case in the set.

## What's wrong

For `ollama/` routes, `litellm/utils.py` rewrites the request's `tools` into a JSON-only prompt and
sets `format: "json"`. The model then replies with a JSON object describing the call it wants to
make.

On the non-streaming path, `transform_response` parses that buffered body into `tool_calls`.

`OllamaTextCompletionResponseIterator.chunk_parser` has no equivalent. So on the streaming path
the raw JSON goes out as **message content**.

## What the caller sees

- HTTP 200
- `finish_reason` of `"stop"`
- `tool_calls` empty
- a JSON blob where the assistant's message should be

Nothing raises. An agent loop that branches on `tool_calls` simply never fires. A
cancel-and-refund request produces no cancellation, no refund, and a JSON blob in front of the
customer.

## Why it belongs in this collection

It is the Helicone `default` branch wearing different clothes: a code path that produces something
well-formed and plausible, hands it to a caller with no way to tell, and never says a word.

## The fix, and why it took four passes

The conversion is **gated**, not a shape heuristic:

- `transform_request` arms detection only when litellm's own tool prompt has actually been
  injected, so nothing fires on a plain streamed JSON response from a request that never asked
  for tools.
- Synthesised tool calls are restricted to the functions the request actually offered.
  `get_optional_params` passes on the schemas it rewrote, so the offered names survive to the
  point where the stream is parsed.

Worth stating plainly: the first two attempts scored 3/5 on the repo's automated review and were
reworked. One version passed unit tests and **broke against a real ollama**, caught only by
running it live, not by CI.

## Reproduce

- Source: `litellm/llms/ollama/completion/transformation.py`, `litellm/utils.py`
- Test: `tests/test_litellm/llms/ollama/test_ollama_completion_transformation.py`

```bash
gh pr checkout 34769 --repo BerriAI/litellm
git checkout origin/litellm_internal_staging -- litellm/llms/ollama/completion/transformation.py litellm/utils.py
python -m pytest tests/test_litellm/llms/ollama/test_ollama_completion_transformation.py -q
```

**Credit:** issue [#19742](https://github.com/BerriAI/litellm/issues/19742) was filed by
[@rcmurphy](https://github.com/rcmurphy) and closed by a stale bot. I wrote the fix, not the
report.
