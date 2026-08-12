# Wrong numbers

Every library below reports at least one number that comes out wrong while nothing raises.
**44 pull requests across 28 organisations. 9 merged upstream after human review.**

I also thought these defects cluster in metric code because metric code is untested. I tried to
measure that twice. The first method grepped test files for each metric's name, which measures
naming convention rather than coverage. The second was meant to fix it by running the suite
under coverage, and produced a figure I could not reproduce afterwards and which appears to have
been counting modules that failed to import. Both are withdrawn, and the page arguing them is
deleted rather than patched.

So I no longer claim to know why these defects cluster where they do. What is below is the
defects themselves, each one reproduced against an installed package, and most of them shipping
a test that fails on `main`.

> ### The checker lives here now: [cachecheck](https://github.com/arthi-arumugam-git/cachecheck)
>
> `cachecheck.py` used to sit in this repo. It is its own package now, because a tool people
> can run is worth more than a tool people can read about, and two copies of it would have
> drifted apart, which is the exact defect this whole repo is about.
>
> ```bash
> uvx cachecheck .
> ```
>
> No dependencies, exit code 1 on a finding, and it ships as a GitHub Action. Every rule in it
> is one of the findings written up below.

Every finding links to a pull request, and nearly all of them ship a test that fails on
`main`. The exceptions are the one-line changes and the price-data updates, where there is
nothing meaningful to assert. You do not have to take my word for any of it, and the index
below is generated from the GitHub API rather than maintained by hand, because a page arguing
that stale numbers go unnoticed has no business carrying one. See
[How to check this yourself](#how-to-check-this-yourself).

**[Jump to the full index of every finding and its status.](#the-findings)**


**The fifth framework, and the worst variant of the five.**
[`mcp-use#2127`](findings/mcp-use-2127-streamed-usage-erased.md). Anthropic's streaming
`message_delta` carries `output_tokens` and nothing else, and the usage parser returns every
key with the absent ones set to `undefined`, so a spread merge overwrote the counters captured
at `message_start`. After any streamed call the input side of the accounting was not wrong, it
was **gone**: an end-to-end test reports `totalTokens: undefined` on the base commit. Their
review then surfaced a third copy of the same arithmetic that I had missed, which is written
up honestly in the finding.

**Same defect, two of three files, twice in one week.** Both of these are a fix that landed on
some of a set of near-identical files and not the rest, leaving two implementations of one
contract quietly disagreeing:

- [`supervision#2468`](findings/supervision-2468-recall-prediction-only-classes.md) closes
  `supervision#2467`. `Precision` and `F1Score` were taught to track classes that appear only in
  predictions; `Recall` was missed, so the three metrics disagree about which classes exist for
  identical input and their per-class arrays cannot be zipped. `test_recall.py` is also the only
  metric test file with no coverage for that case.
- [`inference#2748`](findings/inference-2748-gateway-proxy-parity.md) closes `inference#2662`,
  filed by Roboflow. A secure-gateway URL builder had drifted from its sibling twice: no
  idempotence guard, so an already-wrapped URL got proxied twice, and the gateway's base path
  was silently dropped, sending weights traffic somewhere the server traffic did not go.

**Status is in the index below, per finding, generated from the API.** Of the nine merged,
`inspect_evals#2036`, `#2042` and `#2097` went in at the UK AI Security Institute, `pipecat#5163`
at Daily about four hours after it opened, `livekit/agents#6663` was approved and merged by
LiveKit's co-founder, `supervision#2468` and `inference#2745` at Roboflow, the first after a review that caught a real
hole in my first attempt and the second approved by two maintainers, `haystack-core-integrations#3717` at deepset after a round of requested
changes, and `genai-prices#520` at Pydantic. Nine were closed unmerged, and four of those were closed as
duplicates of a fix that landed instead: `phoenix#14761` (superseded by @Anuj7411's own PR, which
also closed the issue mine claimed to close), `inference#2748` (by #2747, opened hours earlier),
`crewAI#6838` (by a maintainer's own #6844) and `respan#339` (by #344). The rest:
`verifiers#2176` closed in a triage sweep, `llama_index#22548` where the callback system is
deprecated, `deepeval#2995` self-closed as obsolete, `superset#33377` on a botched rebase, and
`inspect_scout#9` which I closed myself once I found upstream had shipped the fix in June.

Current state for all of them, unfiltered:
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

I spent a month reading the numeric paths of LLM eval, tracing and cost-tracking libraries.
44 pull requests came out of it, across deepeval, Phoenix, LiteLLM, Helicone, Langfuse,
OpenLLMetry, Judgeval, Vellum, Okareo, the Cohere SDK, Pydantic's Logfire and genai-prices,
respan, UK AISI's inspect_evals, Pipecat, Prime Intellect's verifiers, mcp-use, crewAI,
Roboflow's supervision and inference, FiftyOne, LlamaIndex, autoevals, Haystack and others.

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
suites. I do not have a measurement of how well the numeric paths specifically are covered; I
tried twice and withdrew both attempts. What I can say is why the test that would catch these
is the one that tends not to get written. You write a test that asserts a call doesn't blow up. You write
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

44 pull requests across 28 organisations is less impressive than it sounds. They are one bug
pattern found repeatedly, not 44 independent investigations. Once you know the shape (a `default`, a truthiness check, a denominator that
isn't the thing you counted) finding the next one is grep and forty minutes.

The sample is also small and it is not random. I picked these libraries because they're the ones
I use.

## The findings

As of 2026-08-08, nine have been merged after human review. `inspect_evals#2036`, `#2042` and
`#2097` at the UK AI Security Institute, `pipecat#5163` at Daily about four hours after it opened,
`livekit/agents#6663` approved and merged by LiveKit's co-founder, `supervision#2468` and
`inference#2745` at Roboflow,
`haystack-core-integrations#3717` at deepset, and `genai-prices#520` at Pydantic. On the first two
inspect_evals fixes the maintainer pushed commits before merging, so those merged diffs are not
purely mine. Nine were closed unmerged, listed above. The rest are open, and many are
still unreviewed by a human.

If you maintain one of these and I've got something wrong, open an issue here or comment on
the PR and I'll fix or withdraw it.

**44 pull requests across 28 organisations. 9 merged upstream after human review.**

| Status | Where | What was wrong | PR |
|---|---|---|---|
| **merged** | `UKGovernmentBEIS/inspect_evals` | stop scoring truncated reasoning as the model's answer | [#2097](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2097) |
| **merged** | `roboflow/inference` | stop usage tracking failures from failing the inference call | [#2745](https://github.com/roboflow/inference/pull/2745) |
| **merged** | `pydantic/genai-prices` | Add AWS Bedrock prices for Writer Palmyra X4 and X5 | [#520](https://github.com/pydantic/genai-prices/pull/520) |
| **merged** | `deepset-ai/haystack-core-integrations` | include cached tokens in the OpenAI-compatible prompt_tokens | [#3717](https://github.com/deepset-ai/haystack-core-integrations/pull/3717) |
| **merged** | `roboflow/supervision` | track prediction-only classes in Recall | [#2468](https://github.com/roboflow/supervision/pull/2468) |
| **merged** | `livekit/agents` | count cached tokens in Bedrock's prompt_tokens | [#6663](https://github.com/livekit/agents/pull/6663) |
| **merged** | `UKGovernmentBEIS/inspect_evals` | stop penalising optional parameters at their schema default | [#2042](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2042) |
| **merged** | `UKGovernmentBEIS/inspect_evals` | restore the denominator on confidence and apologize_rate | [#2036](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2036) |
| **merged** | `pipecat-ai/pipecat` | count cached input tokens in total_tokens for Anthropic and Bedrock | [#5163](https://github.com/pipecat-ai/pipecat/pull/5163) |
| open | `respanai/respan` | add control cases for the thinking-token fold | [#351](https://github.com/respanai/respan/pull/351) |
| open | `voxel51/fiftyone` | compute per-sample Dice from the sample's own confusion matrix | [#8195](https://github.com/voxel51/fiftyone/pull/8195) |
| closed | `crewAIInc/crewAI` | count cached input tokens in the reported totals | [#6838](https://github.com/crewAIInc/crewAI/pull/6838) |
| open | `armature-tech/mcp-analytics-python` | stop the overflow warning reporting a count that is always 1 | [#3](https://github.com/armature-tech/mcp-analytics-python/pull/3) |
| open | `mcp-use/mcp-use` | count Anthropic cache tokens and stop message_delta erasing usage | [#2127](https://github.com/mcp-use/mcp-use/pull/2127) |
| closed | `roboflow/inference` | align weights proxy builder with wrap_url (#2662) | [#2748](https://github.com/roboflow/inference/pull/2748) |
| open | `braintrustdata/autoevals` | stop a skipped sub-score being averaged as a mismatch | [#210](https://github.com/braintrustdata/autoevals/pull/210) |
| open | `UKGovernmentBEIS/inspect_evals` | score proof rearrangement against the ground truth length | [#2060](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2060) |
| open | `reef-technologies/django-business-metrics` | the documented collection timeout can never fire, and one failing metric blanks the whole pagee page | [#8](https://github.com/reef-technologies/django-business-metrics/pull/8) |
| closed | `confident-ai/deepeval` | unbreak npm ci by aligning the ai devDependency with the mastra peer range | [#2995](https://github.com/confident-ai/deepeval/pull/2995) |
| closed | `run-llama/llama_index` | count Anthropic cached prompt tokens in TokenCountingHandler | [#22548](https://github.com/run-llama/llama_index/pull/22548) |
| open | `pipecat-ai/pipecat` | report accumulated TTS usage when a turn is interrupted | [#5188](https://github.com/pipecat-ai/pipecat/pull/5188) |
| closed | `PrimeIntellect-ai/verifiers` | fall back to loopback TCP where zmq has no ipc transport | [#2176](https://github.com/PrimeIntellect-ai/verifiers/pull/2176) |
| open | `pydantic/logfire` | price Bedrock calls under the aws provider | [#2162](https://github.com/pydantic/logfire/pull/2162) |
| closed | `respanai/respan` | fold Gemini thinking tokens into the output token count | [#339](https://github.com/respanai/respan/pull/339) |
| open | `JudgmentLabs/judgeval` | fix: don't adopt a foreign global OTel span as a Judgment parent | [#769](https://github.com/JudgmentLabs/judgeval/pull/769) |
| open | `okareo-ai/okareo-python-sdk` | keep temperature=0 when reading a driver from the API | [#260](https://github.com/okareo-ai/okareo-python-sdk/pull/260) |
| open | `okareo-ai/okareo-python-sdk` | pass timeout through to the HTTP client | [#261](https://github.com/okareo-ai/okareo-python-sdk/pull/261) |
| open | `confident-ai/deepeval` | normalize ConversationalGEval score against the rubric range | [#2965](https://github.com/confident-ai/deepeval/pull/2965) |
| open | `confident-ai/deepeval` | correct accuracy denominators in EquityMedQA and GSM8K | [#2966](https://github.com/confident-ai/deepeval/pull/2966) |
| open | `confident-ai/deepeval` | stop HumanEval collapsing pass@k into pass@n | [#2967](https://github.com/confident-ai/deepeval/pull/2967) |
| open | `confident-ai/deepeval` | score ToolUseMetric correctly when no tool was needed | [#2968](https://github.com/confident-ai/deepeval/pull/2968) |
| open | `BerriAI/litellm` | select one pricing tier from request input size | [#34760](https://github.com/BerriAI/litellm/pull/34760) |
| open | `Helicone/helicone` | reach higher pricing tiers on non-tiered providers | [#5737](https://github.com/Helicone/helicone/pull/5737) |
| open | `BerriAI/litellm` | emit streamed tool calls instead of raw JSON content | [#34769](https://github.com/BerriAI/litellm/pull/34769) |
| open | `BerriAI/litellm` | start on consoles that cannot encode the startup banner | [#34770](https://github.com/BerriAI/litellm/pull/34770) |
| closed | `Arize-ai/phoenix` | carry LiteLLM above_NNNk tier rates into the manifest | [#14761](https://github.com/Arize-ai/phoenix/pull/14761) |
| open | `cohere-ai/cohere-python` | batched embed drops meta.tokens and image billed units | [#784](https://github.com/cohere-ai/cohere-python/pull/784) |
| open | `cohere-ai/cohere-python` | save_csv writes a blank row between every record on Windows | [#785](https://github.com/cohere-ai/cohere-python/pull/785) |
| open | `langfuse/langfuse-python` | stop dropping cost when usage is a dict or cost is an int | [#1781](https://github.com/langfuse/langfuse-python/pull/1781) |
| open | `vellum-ai/vellum-python-sdks` | Exclude unpopulated values from get_mean_metric_output denominator | [#3741](https://github.com/vellum-ai/vellum-python-sdks/pull/3741) |
| open | `traceloop/openllmetry` | stop double-counting output tokens on streamed messages | [#4377](https://github.com/traceloop/openllmetry/pull/4377) |
| open | `pingcap/ossinsight` | Add whatbroke to AI Evaluation & Testing collection | [#3102](https://github.com/pingcap/ossinsight/pull/3102) |
| open | `ollama/ollama` | Add whatbroke to community integrations | [#17344](https://github.com/ollama/ollama/pull/17344) |
| closed | `apache/superset` | add column required validation for filter_select | [#33377](https://github.com/apache/superset/pull/33377) |
Credit where it is not mine: the diagnosis behind `inspect_evals#2036` is
[@dewstend's](https://github.com/UKGovernmentBEIS/inspect_evals/issues/1979), and the defect
and examples behind `inspect_evals#2042` are
[@wise-east's](https://github.com/UKGovernmentBEIS/inspect_evals/issues/2004). What is mine on
both is the fix, the sweep that measured how far it reaches, and the tests; on #2036 also the
demonstration that the fix the issue proposes reports a *different* wrong number, 0.15 against
a correct 0.2727. Five more began as someone else's bug report and are credited in their own files:
`Helicone#5737` and `Phoenix#14761` from issues filed by @Anuj7411, `litellm#34769` from
@rcmurphy, `inference#2748` from @alexnorell, and `logfire#2162` from @ldbolanos. On each of
those I wrote the fix, not the report.

One is written up as a **negative result**:
[LiteLLM #30135](findings/not-a-bug-litellm-30135.md), a reported bug chased, reproduced, and
shown not to be a bug at all. It is here at the same length as the real ones, because a record
that only ever confirms is not evidence of a working method.

Long-form write-ups for the findings that have them are in
[`findings/`](findings/), one file per defect.

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
