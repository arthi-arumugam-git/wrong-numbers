# Every LLM eval and cost library I checked reports at least one wrong number

Twenty-five pull requests across fifteen companies. Sixteen of them are the same defect:
a number comes out wrong and nothing raises.

Every finding here links to a pull request, and every pull request ships a test that fails
on `main`. You do not have to take my word for any of it. See
[How to check this yourself](#how-to-check-this-yourself).

**Status, updated 2026-08-02.** Three have been merged upstream: `inspect_evals#2036` and
`inspect_evals#2042` at the UK AI Security Institute, and `pipecat#5163` at Daily. One,
`verifiers#2176`, was closed unmerged during a repository triage sweep, and the issue it
fixes is still open. The rest are open. Current state for all of them, without my
summarising it:
[`is:pr author:arthi-arumugam-git`](https://github.com/search?q=is%3Apr+author%3Aarthi-arumugam-git&type=pullrequests).

---

Here is a line from deepeval's HumanEval benchmark:

```python
prediction, score = self.predict(model, task, golden, k).values()
if score:
    task_correct = 1
    overall_correct_predictions += 1
```

`score` is pass@k. It's a probability in `[0, 1]`, not a flag. `Scorer.pass_at_k(n, c, k)`
returns something non-zero whenever at least one of the `n` samples passes, so `if score:`
counts that task as a full pass, which is pass@n, no matter what `k` you asked for. The `k`
argument to `evaluate()` has no effect on the reported number.

At the default `n=200, k=1`, a task where 1 of 200 samples passes has a true pass@1 of 0.005
and is reported as `1.0`. A model that stumbles onto each solution once in two hundred attempts
scores 100% on HumanEval. That's the benchmark people put in papers.

I spent a week reading the numeric paths of LLM eval, tracing and cost-tracking libraries.
Twenty-five pull requests came out of it: deepeval, Phoenix, LiteLLM, Helicone, Langfuse,
OpenLLMetry, Judgeval, Vellum, Okareo, the Cohere SDK, Pydantic's Logfire and genai-prices,
respan, UK AISI's inspect_evals, Pipecat, and Prime Intellect's verifiers.

What I want to write about isn't the individual bugs. It's that they're all the same shape.

## The shape

Here's the one that makes the argument for me, from Helicone's cost package.
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

Four providers handled. Everything else returns a constant zero. `getPricingTier` picks the
highest tier whose threshold is `<=` the value it's given, so zero always selects the cheapest
tier, and every higher tier on every other provider is unreachable.

A `gpt-5.4` request at 300,000 input and 50,000 output tokens bills at $1.50. The correct
figure, once the above-272K tier applies, is $2.625. Forty-three percent under, on exactly the
requests that cost the most.

I scanned every endpoint config in the repo for `pricing.length > 1` to size it: 40 endpoints
declare more than one tier, and 24 of them sit on a provider the switch never handled:
azure 2, bedrock 3, helicone 10, openai 2, openrouter 7.

Look at what that `default` branch does. It doesn't throw. It doesn't warn. It returns a value
of the right type that is perfectly valid input to the next function, which does its job
correctly on it and returns a price that is a plausible number. There is no point in that chain
where anything is in a position to notice. It stayed that way across 24 endpoints.

That's the whole thing in one function. Every other item on the list is a variant of it:

- **A denominator that doesn't match what was counted.** Vellum's `get_mean_metric_output`
  filters `None` out of the numerator and divides by the length of the *unfiltered* list, so
  `[1.0, None, 1.0, None]` scores 0.5 instead of 1.0, and an all-`None` run returns 0.0,
  indistinguishable from a real score of zero. deepeval's EquityMedQA scores the first 10
  goldens of each task and divides by all of them; on a 661-golden task a perfect run reports
  0.015.
- **A truthiness check on a value where zero is meaningful.** The HumanEval one above. Okareo's
  driver loader guards every field with `if response.temperature:`, and since that field is a
  required `float` on the response model, the only value the guard can ever filter is a
  legitimate `0`, which becomes the class default of `0.6`. Worse, `to_dict()` is what the
  update call posts, so a get-then-save round trip rewrites the stored `0` server-side and a
  deterministic driver quietly stops being deterministic.
- **A fallback that substitutes a default.** Helicone's `return () => 0`.
- **A guard that was correct in one code path and never applied to its twin.**
  `ConversationalGEval` accepts a rubric but hard-codes 0-10 in both the prompt template and the
  normalizer, so a perfect 5 on a 0-5 rubric reports 0.5, while `GEval` given the identical
  rubric and the identical raw score reports 1.0. That's not an oversight nobody caught.
  deepeval fixed exactly this in `g_eval.py` in PR #1915, merged last August. The fix was
  correct. It just never reached the conversational variant, and the shared `get_score_range`
  helper it introduced was sitting right there.

Then there's the sync-script version, which I like because nobody wrote a bug at all. Phoenix
builds its cost manifest from LiteLLM's pricing data via `sync_models.py`, and that script reads
only the flat rate fields. LiteLLM also publishes `input_cost_per_token_above_200k_tokens` and
friends: whole-prompt tier rates that replace the base rate outright once the prompt exceeds
the threshold. The script never matched them, so the shipped manifest carried **zero**
threshold-based customizations across 267 models.

Nothing downstream was wrong. `ThresholdBasedTokenPriceCustomization` and its calculator both
work correctly; they were simply never handed anything to do. Regenerating the manifest with the
tier extraction in place produces 77 customizations across 23 models. `gemini-2.5-pro` goes from
1.25e-6 flat to 2.5e-6 above 200K, a straight 2x under-bill on every long-prompt trace until
then.

## The same silence, somewhere other than a number

The most vivid one on the list isn't a number at all.

LiteLLM's `ollama/` route drops **every** tool call when `stream=true`. The non-streaming path
parses the buffered body into `tool_calls`; the streaming iterator has no equivalent, so the raw
JSON goes out as message content. HTTP 200, `finish_reason` of `"stop"`, nothing raises. A
cancel-and-refund request produces no cancellation, no refund, and a JSON blob in front of the
customer.

It belongs next to the Helicone `default` branch rather than in the numeric list, because it's
the identical failure mode wearing different clothes: a code path that produces something
well-formed and plausible, hands it to a caller with no way to tell, and never says a word.

## The obvious fix is often wrong in the same way

This is the part I'd want a maintainer to take from it.

The filed issue on the Helicone bug proposed adding four provider cases returning
`input + cachedInput`. That fix looks complete. It fixes the reported symptom, it passes review,
and it leaves bedrock broken and mis-tiers every Anthropic-authored model resold through
OpenRouter or Helicone, because that provider bills cache writes as part of the prompt, which
is why the existing `anthropic` case adds `write5m` and `write1h`. The threshold basis keys off
the model's *author*, not the serving provider. Get that backwards and you ship a fix that is
silently wrong in exactly the way the original was.

The reason that trap exists is the same reason the bug existed: nothing in the system can tell
you the number is wrong. You have to derive it from the provider's billing rules and check.

## The one that wasn't a bug

I also spent a day on LiteLLM issue #30135, which reports that `*_above_200k_tokens` rates
configured via `model_info` are ignored and the base rate is applied flat. Good report,
specific, with spend-log evidence.

It isn't a bug. I reproduced the reporter's exact config through the full Router → logging path
and got `response_cost = 7.3211525`. Flat base-rate would have been 3.66036875. The tiered rates
are carried through and applied.

The reporter's evidence is real and does reproduce. The above-200k fields genuinely show as
`null` in the stored `model_map_information`. It just doesn't mean what it looks like it means.
`_response_cost_calculator` resolves pricing through the deployment, carrying `router_model_id`.
`get_model_cost_information`, which builds the spend-log map, calls
`litellm.get_model_info(model=model_cost_name, custom_llm_provider=...)`, a name-based lookup on
the shared `{provider}/{model}` key, which by design doesn't carry per-deployment pricing. Cost
right, logged map misleading.

The rest of the gap is that the expected figure assumed graduated, income-tax-style pricing,
where these providers switch the whole request to the higher rate. Which is a real defect, just
in a different library: LiteLLM's own DashScope calculator *does* apply graduated slicing, and
Alibaba Model Studio doesn't bill that way. It picks one tier from the request's total input and
charges everything at that tier. A 300k-input `qwen-flash` request logs at $0.0246 against the
$0.079 actually charged. 69% under.

I'm including the non-bug because "I checked N libraries and all N were wrong" is the kind of
claim that deserves the obvious objection: you went looking for wrongness. Fair. So here's a case
where the evidence looked exactly as damning and the number was correct. Verify before you
assert, including against yourself.

Full write-up: [`findings/not-a-bug-litellm-30135.md`](findings/not-a-bug-litellm-30135.md).

## Two more, found after this was written

Both are in Pipecat, Daily's voice-agent framework, and both are the same shape as
everything above. I'm adding them here rather than folding them into the count, because the
sixteen were one week's sweep and these came later.

The first is the cross-provider version. `LLMTokenUsage.total_tokens` did not mean the same
thing depending on which service produced it. OpenAI and Google take the total straight from
the provider, and both count cache reads inside it. The Anthropic and Bedrock services
computed `prompt_tokens + completion_tokens` locally, against an input count that is already
net of the prompt cache, so every cached token fell out of the total. In a voice agent the
system prompt and the conversation history are re-read from cache every turn, so cache reads
dominate within a few turns: a turn billed for 2100 input tokens with 2000 of them cached
reported 150.

What makes it a good example of the class is that the correct sum was already in the same
function. `_process_context` computes
`prompt_tokens + cache_creation_input_tokens + cache_read_input_tokens` for its own caching
threshold check, on the same values, a few lines above the reporting call that left both
cache terms out. Nothing reconciled the two.
[pipecat#5163](https://github.com/pipecat-ai/pipecat/pull/5163), merged.

The second is a drift bug, and it is the one I'd point at if I could only keep one. In
token-streaming mode the per-token usage calls short-circuit and the text accumulates into
`_streamed_text`, reported once when the turn flushes. `_handle_interruption` cleared that
accumulator without reporting it, so an interrupted turn contributed nothing at all, for
text the provider had already been sent and billed for. Barge-in is not an edge case in a
voice agent, and token streaming is the default for one of the TTS services.

The cause is still readable in the source. The comment where the accumulator is filled says
it is there "for a single debug log at flush time". That was true when the interruption
handler was written, and dropping a debug buffer on interruption was correct. The
accumulator later became the input to the billing metric, and the interruption path was
never revisited. Nobody wrote a bug; the meaning of a variable moved underneath a line that
stayed correct-looking.
[pipecat#5188](https://github.com/pipecat-ai/pipecat/pull/5188).

## Why this class in particular

A crash gets fixed in an hour. Someone's build goes red, there's a stack trace, and the stack
trace names the line. A number that is quietly wrong gets shipped, cited, budgeted against, and
used to decide whether last week's prompt change was an improvement.

The blast radius is unusual here because of what these libraries are *for*. They are the
instruments. When the eval framework's denominator is wrong, every model comparison run through
it is wrong by an unknown factor. When the cost manifest is missing tier rates, every
long-context spend report is under by 2x and the finance conversation happens on that number.
Nobody downstream is in a position to find out, because the only signal they get is a float that
looks like a float.

And this tooling is young. Most of it is under three years old, moving fast, with real test
suites, but the numeric paths are the thinnest-covered part of all of them, and I think that's
structural rather than careless. You write a test that asserts a call doesn't blow up. You write
a test that asserts the response shape. Asserting the *value* requires you to independently
derive what the value should be, from a provider's pricing page or a benchmark's definition, and
that's slow, so it's the test that doesn't get written. OpenLLMetry's streaming test already
asserted `input_tokens == 17` and the `input + output == total` identity. It never asserted the
output value, which is the one that was double-counted, 174 against a true 171, so the bug
passed CI for as long as it existed.

I don't have a tidy moral. "Write value assertions" is true and useless; everyone knows. The one
thing I'd actually change is narrower: when you write a `default` branch, a `try/except`, or an
`if value:` in a path that produces a number a user will read, that's the moment to ask what
happens if it's hit and whether anyone will ever know. In every case above, the answer was no.

## On the size of the claim

Sixteen wrong numbers in thirteen libraries in a week is less impressive than it sounds, and
it's worth saying so plainly. They are one bug pattern found sixteen times, not sixteen
independent investigations. Once you know the shape (a `default`, a truthiness check, a denominator that
isn't the thing you counted) finding the next one is grep and forty minutes.

The sample is also small and it is not random. I picked these libraries because they're the ones
I use.

## The findings

As of 2026-08-02, three have been merged after human review: `inspect_evals#2036` and
`inspect_evals#2042`, both merged by a UK AI Security Institute maintainer who pushed
follow-up commits first, and `pipecat#5163`, merged by a Daily maintainer about four hours
after it was opened. So the merged diffs are not purely mine. One, `verifiers#2176`, was
closed unmerged in a repository triage sweep that also closed several maintainers' own PRs;
the issue it fixes is still open. The rest are open, and most are still unreviewed by a
human.

If you maintain one of these and I've got something wrong, open an issue here or comment on
the PR and I'll fix or withdraw it.

### Wrong numbers (16)

| # | Library | Finding | PR |
|---|---|---|---|
| 1 | deepeval | [HumanEval collapses pass@k into pass@n](findings/deepeval-2967-humaneval-pass-at-k.md) | [#2967](https://github.com/confident-ai/deepeval/pull/2967) |
| 2 | deepeval | [Benchmark accuracy denominators don't match what was scored](findings/deepeval-2966-benchmark-denominators.md) | [#2966](https://github.com/confident-ai/deepeval/pull/2966) |
| 3 | deepeval | [ConversationalGEval ignores the rubric range](findings/deepeval-2965-conversational-geval-rubric.md) | [#2965](https://github.com/confident-ai/deepeval/pull/2965) |
| 4 | deepeval | [ToolUseMetric scores 0 when no tool was needed](findings/deepeval-2968-tool-use-metric.md) | [#2968](https://github.com/confident-ai/deepeval/pull/2968) |
| 5 | inspect_evals | [Sycophancy's `confidence` and `apologize_rate` report 0.0 on every run](findings/inspect-evals-2036-sycophancy-metrics.md) | [#2036](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2036) |
| 6 | Phoenix | [LiteLLM tier rates never reach the cost manifest](findings/phoenix-14761-tier-rates.md) | [#14761](https://github.com/Arize-ai/phoenix/pull/14761) |
| 7 | Helicone | [Higher pricing tiers unreachable on 24 endpoints](findings/helicone-5737-unreachable-tiers.md) | [#5737](https://github.com/Helicone/helicone/pull/5737) |
| 8 | LiteLLM | [DashScope tiers each token category independently](findings/litellm-34760-dashscope-tiers.md) | [#34760](https://github.com/BerriAI/litellm/pull/34760) |
| 9 | OpenLLMetry | [Streamed output tokens double-counted](findings/openllmetry-4377-double-counted-tokens.md) | [#4377](https://github.com/traceloop/openllmetry/pull/4377) |
| 10 | Langfuse | [Cost dropped when usage is a dict or cost is an int](findings/langfuse-1781-dropped-cost.md) | [#1781](https://github.com/langfuse/langfuse-python/pull/1781) |
| 11 | Vellum | [Mean metric divides by the unfiltered length](findings/vellum-3741-mean-denominator.md) | [#3741](https://github.com/vellum-ai/vellum-python-sdks/pull/3741) |
| 12 | Okareo | [`temperature=0` overwritten by the class default](findings/okareo-260-temperature-zero.md) | [#260](https://github.com/okareo-ai/okareo-python-sdk/pull/260) |
| 13 | Cohere | [Batched embed drops `meta.tokens` and image billed units](findings/cohere-784-embed-meta-dropped.md) | [#784](https://github.com/cohere-ai/cohere-python/pull/784) |
| 14 | Logfire | [`AnthropicBedrock` calls carry tokens but never a cost](findings/logfire-2162-bedrock-cost-dropped.md) | [#2162](https://github.com/pydantic/logfire/pull/2162) |
| 15 | genai-prices | [Writer Palmyra X4 and X5 on Bedrock resolve no price at all](findings/genai-prices-520-palmyra-bedrock.md) | [#520](https://github.com/pydantic/genai-prices/pull/520) |
| 16 | respan | [Gemini thinking tokens land on no attribute at all](findings/respan-339-gemini-thinking-tokens.md) | [#339](https://github.com/respanai/respan/pull/339) |

Credit where it is not mine: the diagnosis behind #5 is
[@dewstend's](https://github.com/UKGovernmentBEIS/inspect_evals/issues/1979). What is mine there
is the fix, the demonstration that the fix the issue proposes reports a different wrong number,
the repo-wide sweep and the tests. Every other finding on this page is my own.

### The same silence, elsewhere (5)

| # | Library | Finding | PR |
|---|---|---|---|
| 17 | LiteLLM | [`ollama/` drops every tool call when `stream=true`](findings/litellm-34769-ollama-tool-calls.md) | [#34769](https://github.com/BerriAI/litellm/pull/34769) |
| 18 | Judgeval | [A foreign global OTel span is adopted as parent](findings/judgeval-769-foreign-parent-span.md) | [#769](https://github.com/JudgmentLabs/judgeval/pull/769) |
| 19 | Okareo | [`timeout` accepted and never passed to the client](findings/okareo-261-timeout-ignored.md) | [#261](https://github.com/okareo-ai/okareo-python-sdk/pull/261) |
| 20 | Cohere | [`save_csv` writes a blank row between every record on Windows](findings/cohere-785-csv-blank-rows.md) | [#785](https://github.com/cohere-ai/cohere-python/pull/785) |
| 21 | LiteLLM | [Proxy won't start on a console that can't encode the banner](findings/litellm-34770-banner-encoding.md) | [#34770](https://github.com/BerriAI/litellm/pull/34770) |

### Investigated and not filed (1)

| Library | Finding | Issue |
|---|---|---|
| LiteLLM | [Tier rates *are* applied; the reporter's evidence is a logging artifact](findings/not-a-bug-litellm-30135.md) | [#30135](https://github.com/BerriAI/litellm/issues/30135) |

## How to check this yourself

Each finding names the file it changes and the test file it adds. The general recipe:

```bash
gh pr checkout <number> --repo <owner>/<repo>
git checkout origin/main -- <the source file named in the finding>
# run the test file named in the finding
```

That leaves the new test in place and the old source restored, which is the state each finding
reports a failure against. Where a PR touches generated files or a manifest, the finding says so.

Most of these tests need no model, no network and no API key: they construct the response
objects directly or replay a recorded fixture. The exceptions are noted per finding.

## Where this came from

I kept wanting to see a number change when nothing else did, so I built
[whatbroke](https://github.com/arthi-arumugam-git/whatbroke), a CLI that diffs an agent's
behaviour between two runs of the same task: tool calls, arguments, costs and outputs.

Arthi Arumugam · [github.com/arthi-arumugam-git](https://github.com/arthi-arumugam-git)
