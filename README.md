# Wrong numbers

This repository studies one defect class: numbers that come out wrong while nothing raises,
in the libraries the LLM ecosystem uses to measure itself, its evals, its traces and its
bills. The corpus is **52 pull requests across 34 organisations: 9 merged upstream after
human review, 34 open, 9 closed unmerged**, plus one investigation written up as a negative
result. Three of the merged fixes shipped in the UK AI Security Institute's inspect_evals
Release v0.17.0, August 2026. The `findings/` directory holds 31 long-form write-ups, 30
defects and 1 negative result, each reproduced against an installed package and most shipping
a test that fails on `main`. Classified by mechanism, the defects fall into thirteen
recurring shapes, one write-up sitting outside the taxonomy by its own admission, and the
largest single family, an identical cached-token arithmetic error, was found independently
implemented in six unrelated frameworks. The headline result is not any single bug; it is
that the same few shapes recur
across codebases that share no code, which means each shape can be caught by pattern rather
than by luck.

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
[How to check this yourself](#how-to-check-this-yourself). The class-to-finding mapping that
builds every table on this page is [`taxonomy.json`](taxonomy.json), so the index is
regenerable rather than hand-kept.

**[Jump to the taxonomy](#the-taxonomy) ·
[Jump to the prevalence table](#prevalence) ·
[Jump to the full index](#the-findings)**

## The defect class

A crash gets fixed in an hour. Someone's build goes red, there's a stack trace, and the stack
trace names the line. A number that is quietly wrong gets shipped, cited, budgeted against, and
used to decide whether last week's prompt change was an improvement.

The blast radius is unusual here because of what these libraries are *for*. They are the
instruments. When the eval framework's denominator is wrong, every model comparison run through
it is wrong by an unknown factor. When the cost manifest is missing tier rates, every
long-context spend report is under by 2x and the finance conversation happens on that number.
Nobody downstream is in a position to find out, because the only signal they get is a float that
looks like a float.

Every defect below shares one property: the code path produces a value of the right type that
is perfectly valid input to the next function, which does its job correctly on it and returns
something plausible. There is no point in the chain where anything is in a position to notice.

## The taxonomy

The classes below are derived from the defect write-ups in [`findings/`](findings/), by
mechanism rather than by symptom, because the mechanism is the thing you can grep for. Each
finding sits in exactly one primary class and is counted there once; where a finding carries a
second defect it is cross-listed and marked as such. Statuses are from the GitHub API, checked
2026-08-15.

### 1. Cache-token exclusion

**Definition.** A provider reports its input token count net of the prompt cache and bills the
cache counters separately on top. The library maps that net count straight onto
`prompt_tokens` and builds totals from it, so every token served from cache disappears from
the accounting.

**Mechanism.** Anthropic (directly and through Bedrock) sends `input_tokens` excluding
`cache_read_input_tokens` and `cache_creation_input_tokens`, and never sends a total. OpenAI
and Gemini nest their cached counts *inside* the prompt count. Code written against the
OpenAI shape reads the Anthropic shape as if it were complete. The warmer the cache the worse
the number: a call billed at 21,503 tokens reports 3, because the 3 is precisely the part that
was not cached.

**Findings.**

- [`livekit-6663-bedrock-cached-tokens.md`](findings/livekit-6663-bedrock-cached-tokens.md), [livekit/agents#6663](https://github.com/livekit/agents/pull/6663), merged
- [`crewai-6838-anthropic-cached-tokens.md`](findings/crewai-6838-anthropic-cached-tokens.md), [crewAIInc/crewAI#6838](https://github.com/crewAIInc/crewAI/pull/6838), closed unmerged, superseded by a maintainer's own fix
- [`llamaindex-22548-anthropic-cache-tokens.md`](findings/llamaindex-22548-anthropic-cache-tokens.md), [run-llama/llama_index#22548](https://github.com/run-llama/llama_index/pull/22548), closed unmerged, and carrying its own correction: the diagnosis was right and my proposed fix would have double-counted
- [`mcp-use-2127-streamed-usage-erased.md`](findings/mcp-use-2127-streamed-usage-erased.md), [mcp-use/mcp-use#2127](https://github.com/mcp-use/mcp-use/pull/2127), open, which also carries the streaming erasure written up under class 12

Two more members of the family were fixed without long-form write-ups:
[pipecat-ai/pipecat#5163](https://github.com/pipecat-ai/pipecat/pull/5163), merged at Daily
about four hours after it opened, and
[deepset-ai/haystack-core-integrations#3717](https://github.com/deepset-ai/haystack-core-integrations/pull/3717),
merged at deepset after a round of requested changes.

**Spread: six frameworks**, Pipecat, LiveKit, LlamaIndex, Haystack, mcp-use and CrewAI, each
an independent implementation of the same arithmetic error. Three of the six fixes are merged.
This is the widest cross-library spread in the corpus and the reason
[cachecheck](https://github.com/arthi-arumugam-git/cachecheck) exists.

**How to detect it.** Grep for `input_tokens`, `inputTokens` or `prompt_tokens` being assigned
from a provider response with no `cache_read`, `cache_creation`, `cacheRead` or `cacheWrite`
term nearby. The test shape that catches it: construct a usage object where the cached portion
dwarfs the fresh portion, say `input_tokens=3, cache_read_input_tokens=20000`, and assert the
reported prompt count equals the billed count. The strongest version is a parity test:
identical billed work described in the Anthropic shape and the OpenAI shape must produce
identical totals, which is the invariant every member of this family breaks. Beware the
obvious fix: adding any cache field you find double-counts OpenAI and Gemini, whose prompt
counts are already gross. Only the Anthropic-shaped keys can be summed, and only onto a count
known to be net.

### 2. A guard that filters a legal value

**Definition.** A truthiness or type check meant to skip missing data instead filters a legal
value, `0`, an `int` cost, a `dict`, and a default or nothing at all takes its place.

**Mechanism.** `if value:` is false for `0` and `0.0`. `isinstance(cost, float)` is false for
the integer `0` and `2`. `hasattr(usage, "cost")` is false for `{"cost": 0.002}`. In each case
the field is required or reachable, so the guard never protects against the absence it was
written for; the only thing it can ever filter is a real value.

**Findings.**

- [`deepeval-2967-humaneval-pass-at-k.md`](findings/deepeval-2967-humaneval-pass-at-k.md), [confident-ai/deepeval#2967](https://github.com/confident-ai/deepeval/pull/2967), open. `if score:` treats pass@k, a probability, as a flag, so HumanEval reports pass@n whatever `k` you asked for. At the default `n=200, k=1` a true pass@1 of 0.005 reports as 1.0.
- [`okareo-260-temperature-zero.md`](findings/okareo-260-temperature-zero.md), [okareo-ai/okareo-python-sdk#260](https://github.com/okareo-ai/okareo-python-sdk/pull/260), open. `if response.temperature:` on a required float turns a stored `0` into the class default `0.6`, and a get-then-save round trip rewrites the server copy, so a deterministic driver quietly stops being deterministic.
- [`langfuse-1781-dropped-cost.md`](findings/langfuse-1781-dropped-cost.md), [langfuse/langfuse-python#1781](https://github.com/langfuse/langfuse-python/pull/1781), open. Four of five realistic cost shapes are dropped entirely; the invocation records no cost, which reads downstream as free.

**Affected libraries: 3.**

**How to detect it.** Grep for `if response\.` and `if .* else` guards over numeric fields, for
`isinstance(.*(float|int))` on money, and for `hasattr` on objects that can arrive as dicts.
Then check the field's declared type: a truthiness guard on a *required* field is the defect
by inspection, since the only value it can filter is a legal one. The test shape: feed `0`,
`0.0`, an integer, and a dict through every parsing path and assert the value survives.

### 3. Silent-zero metrics

**Definition.** A metric path that failed, or had nothing to score, emits a number on the
metric's own scale instead of failing, and the number is indistinguishable from a real
judgement.

**Mechanism.** A branch that never runs returns its initialisation value. An empty list is
averaged with a divisor forced to 1. A zero sentinel means four different things and three of
them are failures. In the worst case the fabricated value is the *ideal* score: StereoSet's
`ss` scale turns an empty average into 50, which is the number a perfectly unbiased model
earns.

**Findings.**

- [`inspect-evals-2036-sycophancy-metrics.md`](findings/inspect-evals-2036-sycophancy-metrics.md), [UKGovernmentBEIS/inspect_evals#2036](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2036), merged, shipped in v0.17.0. `confidence` and `apologize_rate` reported 0.0 on every run for every model, because the dict branch their bodies were guarded by could never fire under dict-form registration.
- [`inspect-evals-2123-stereoset-unscorable.md`](findings/inspect-evals-2123-stereoset-unscorable.md), [UKGovernmentBEIS/inspect_evals#2123](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2123), open. A run where nothing parsed reports the ideal score; a run where 95% failed to parse can report maximum bias computed from the 5% that survived, with nothing to say so.
- [`deepeval-2968-tool-use-metric.md`](findings/deepeval-2968-tool-use-metric.md), [confident-ai/deepeval#2968](https://github.com/confident-ai/deepeval/pull/2968), open. A conversation that correctly needed no tool scores 0, the same score as picking every tool wrong.

**Affected libraries: 2.**

**How to detect it.** Grep metric bodies for `else 0.0`, `return 0`, `if .* else 0` and
divisors forced to 1 on empty input. The test shape: feed a run where every sample failed to
parse, and a run where the model legitimately declined, and assert the two are
distinguishable, ideally that the empty case returns `nan` or raises rather than any number on
the metric's scale. "The model declined to engage" and "we could not read a single answer" are
different findings and must not produce the same float.

### 4. A denominator that does not match what was counted

**Definition.** The numerator is computed over a filtered or truncated set and the denominator
over the original one, so the reported mean is scaled by a ratio nobody chose.

**Mechanism.** `filter(None, values)` in the numerator over `len(values)` in the denominator.
Scoring `goldens[:10]` and dividing by `len(goldens)`. Dividing by the requested `n_problems`
rather than the problems that exist.

**Findings.**

- [`vellum-3741-mean-denominator.md`](findings/vellum-3741-mean-denominator.md), [vellum-ai/vellum-python-sdks#3741](https://github.com/vellum-ai/vellum-python-sdks/pull/3741), open. `[1.0, None, 1.0, None]` scores 0.5; an all-`None` run returns 0.0, indistinguishable from a real score of zero.
- [`deepeval-2966-benchmark-denominators.md`](findings/deepeval-2966-benchmark-denominators.md), [confident-ai/deepeval#2966](https://github.com/confident-ai/deepeval/pull/2966), open. EquityMedQA scores 10 goldens and divides by all of them, so a perfect run on a 661-golden task reports 0.015. GSM8K accepts `n_problems=5000`, runs the 1319 that exist, and a perfect model reports 0.264.

**Affected libraries: 2.**

**How to detect it.** Grep for divisions where the numerator side mentions `filter`,
`isinstance`, a slice, or a comprehension with an `if`, and the denominator is a bare `len()`.
The test shape: score a list containing `None`s or a truncated subset and assert a perfect run
reports 1.0, and separately that an all-empty run raises rather than reporting 0.0.

### 5. The fix lands on some twins and not others

**Definition.** Near-identical sibling implementations of one contract exist, a fix or feature
lands on some of them, and the siblings quietly disagree from then on.

**Mechanism.** Nothing forces the siblings to agree. `precision.py` and `f1_score.py` were
taught to track prediction-only classes and `recall.py` beside them was not, so the three
metrics disagree about which classes exist for identical input and their per-class arrays
cannot be zipped. deepeval fixed rubric normalisation in `g_eval.py` in August 2025 and the
fix never reached `conversational_g_eval.py`, with the shared helper it introduced sitting
right there. One URL wrapper gained an idempotence guard and its sibling did not. One of four
instrumentation packages folds thinking tokens and three do not.

**Findings.**

- [`supervision-2468-recall-prediction-only-classes.md`](findings/supervision-2468-recall-prediction-only-classes.md), [roboflow/supervision#2468](https://github.com/roboflow/supervision/pull/2468), merged
- [`deepeval-2965-conversational-geval-rubric.md`](findings/deepeval-2965-conversational-geval-rubric.md), [confident-ai/deepeval#2965](https://github.com/confident-ai/deepeval/pull/2965), open. A perfect 5 on a 0-5 rubric reports 0.5; `GEval` on the identical input reports 1.0.
- [`inference-2748-gateway-proxy-parity.md`](findings/inference-2748-gateway-proxy-parity.md), [roboflow/inference#2748](https://github.com/roboflow/inference/pull/2748), closed unmerged, superseded by a PR opened hours earlier. The drift here fails silently in the direction of less security: weights fetched from somewhere other than the configured gateway.
- [`respan-339-gemini-thinking-tokens.md`](findings/respan-339-gemini-thinking-tokens.md), [respanai/respan#339](https://github.com/respanai/respan/pull/339), closed unmerged, superseded. 800 thinking tokens land on no attribute at all, and on Gemini 2.5 Pro pricing that under-reports output cost by about 94% on the demonstrated call.

**Affected libraries: 4.**

**How to detect it.** When a fix lands, grep the rest of the repository for the exact line it
replaced; the sibling still carrying it is the finding. Diff files that share a naming pattern
(`precision.py`/`recall.py`/`f1_score.py`, `_translator.py` across packages) and treat any
asymmetry as a question. The test shape is an invariant test across siblings: the same input
through each implementation must produce the same class set, the same shape, the same wrapped
URL. In supervision the asymmetry was visible in the test tree itself: four metric test files
covered the prediction-only case and `test_recall.py` was the one that did not, which is
checkable in seconds.

### 6. A schema default scored as a disagreement

**Definition.** The scorer holds the function schema but never reads parameter defaults, so an
optional parameter stated at its own default and the same parameter omitted are scored as
disagreeing, in both directions.

**Findings.**

- [`inspect-evals-2042-bfcl-optional-defaults.md`](findings/inspect-evals-2042-bfcl-optional-defaults.md), [UKGovernmentBEIS/inspect_evals#2042](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2042), merged, shipped in v0.17.0. Sweeping the eight scored BFCL categories found 61 parameter occurrences where an equivalent call scores as a disagreement, against 1281 boundary cases where the ground truth states a non-default and omission must keep failing. The boundary is 21x larger than the bug, which is why the naive fix, ignoring optional parameters, would have been a worse defect than the one it fixed.

**Affected libraries: 1.**

**How to detect it.** The test shape is the pair: ground truth omits and model states the
default, ground truth states the default and model omits, both must score as agreement, plus
guards pinning that a *non*-default value still fails. Measure the boundary before fixing:
count how many ground-truth items state a value different from the declared default, because
that number is the blast radius of the lazy fix.

### 7. Truncation scored as the answer

**Definition.** A generation that stops inside an unterminated block is scored as if the
truncated reasoning were the model's answer.

**Findings.**

- [UKGovernmentBEIS/inspect_evals#2097](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2097), merged, shipped in v0.17.0: LiveBench no longer scores a generation that stops inside an unterminated `<think>` block as the answer, and now matches the reference harness. This one has no long-form write-up in `findings/`; the PR is the record.

**Affected libraries: 1.**

**How to detect it.** Feed the scorer a generation cut off mid-reasoning, inside an
unterminated tag or fence, and assert it is scored as unanswered rather than as whatever
string the truncation left behind. Diff against the benchmark's reference harness where one
exists; "matches the reference implementation" is the checkable claim.

### 8. Aggregate written where the per-sample value belongs

**Definition.** A per-sample field is computed from a dataset-wide accumulator, so every
sample's value drifts toward the running mean and depends on iteration order.

**Findings.**

- [`fiftyone-8195-cumulative-dice.md`](findings/fiftyone-8195-cumulative-dice.md), [voxel51/fiftyone#8195](https://github.com/voxel51/fiftyone/pull/8195), open. Accuracy, precision and recall on the lines directly above use the sample's own matrix; only Dice reaches for the accumulator, whose parameter shares the accumulator's name, so the call reads as correct. Present since 2023.

**Affected libraries: 1.**

**How to detect it.** Grep for `+=` on a matrix or counter followed by a per-sample assignment
that references the accumulated name rather than the local one; shadowed names between a
call site and a parameter are the tell. The test shape is the order test: evaluate the same
data forward and reversed and assert every sample keeps its score. A cumulative value is order
dependent, so this fails on the defect and passes on the fix, and order dependence is
precisely why nobody saw it.

### 9. Pricing tiers unreachable or mis-modeled

**Definition.** Multi-tier pricing exists in the data, and the code that selects a tier either
cannot reach the higher tiers, applies the wrong tier-selection model, or never carries the
tier data to the consumer at all.

**Mechanism.** Three variants, one per finding. A `default` branch returns a constant 0, and
since tier selection takes the highest threshold `<=` the value, zero always selects the
cheapest tier. A calculator applies graduated, income-tax-style slicing to a provider that
actually switches the whole request to one tier. A sync script reads only the flat rate fields,
so the downstream calculator, correct and fully tested, is never handed anything to do.

**Findings.**

- [`helicone-5737-unreachable-tiers.md`](findings/helicone-5737-unreachable-tiers.md), [Helicone/helicone#5737](https://github.com/Helicone/helicone/pull/5737), open. 40 endpoints declare more than one tier and 24 sit on a provider the switch never handled: 43% under-billing on exactly the requests that cost the most.
- [`litellm-34760-dashscope-tiers.md`](findings/litellm-34760-dashscope-tiers.md), [BerriAI/litellm#34760](https://github.com/BerriAI/litellm/pull/34760), open. A 300k-input `qwen-flash` request logs at $0.0246 against the $0.079 actually charged, 69% under.
- [`phoenix-14761-tier-rates.md`](findings/phoenix-14761-tier-rates.md), [Arize-ai/phoenix#14761](https://github.com/Arize-ai/phoenix/pull/14761), closed unmerged, superseded by the issue reporter's own PR. The shipped manifest carried zero threshold customizations across 267 models; regenerating with tier extraction produces 77 across 23, and `gemini-2.5-pro` is a straight 2x under-bill on every long-prompt trace until then.

**Affected libraries: 3.**

**How to detect it.** For every model with more than one published tier, price one request
above the threshold and compare against the provider's own bill; that is the whole test, and
none of the three libraries had it. Grep tier-selection switches for their `default` branch
and ask what a constant return value selects. For sync scripts, diff the set of fields the
source publishes against the set the script matches; the fields it never mentions are the
finding.

### 10. Missing price data, and cost silently dropped

**Definition.** The price for a real model is absent, or the cost lookup fails, and an
exception handler or a skip turns that into a span with token counts and an empty cost column.

**Mechanism.** `calc_price` raises `LookupError`, an `except Exception: pass` swallows it, and
because tokens were set before that block the failure reads as "prices missing for Bedrock"
rather than as an error. Or the provider file simply has no entry for a model the SDK itself
advertises, so the lookup returns `None` and the caller skips setting cost.

**Findings.**

- [`genai-prices-520-palmyra-bedrock.md`](findings/genai-prices-520-palmyra-bedrock.md), [pydantic/genai-prices#520](https://github.com/pydantic/genai-prices/pull/520), merged. Two real Bedrock model references priced at nothing.
- [`logfire-2162-bedrock-cost-dropped.md`](findings/logfire-2162-bedrock-cost-dropped.md), [pydantic/logfire#2162](https://github.com/pydantic/logfire/pull/2162), open. Every `AnthropicBedrock` call carries tokens and no cost, while genai-prices resolves all of the model IDs correctly under `aws` today; the defect is a hardcoded `provider_id='anthropic'` and the swallowed lookup.

`langfuse#1781` in class 2 has the same *effect*, a recorded call with no cost that reads as
free, through a different mechanism, and is counted there.

**Affected libraries: 2.**

**How to detect it.** Assert that every model name the SDK advertises resolves a price; the
genai-prices test is literally `assert None is not None` failing on `main`. Count cost
assertions per integration test file: Logfire's Bedrock test file had zero `operation.cost`
assertions against 27 in its plain Anthropic twin, and the snapshot had encoded the missing
cost as expected output. A snapshot test ratifies whatever the code did on the day it was
recorded, including the bug.

### 11. Config accepted and silently ignored

**Definition.** A parameter exists on the public signature, is accepted without complaint, and
is never wired to anything, so setting it does nothing and its absence can even remove a
protection the underlying library would have provided.

**Findings.**

- [`okareo-261-timeout-ignored.md`](findings/okareo-261-timeout-ignored.md), [okareo-ai/okareo-python-sdk#261](https://github.com/okareo-ai/okareo-python-sdk/pull/261), open. `timeout` is accepted and never passed; the client then constructs `httpx.Client(timeout=None)`, which disables httpx's own 5 second default, so a hung connection hangs forever. A regression from a refactor that replaced the client and left the parameter on the signature.

Two findings in other classes have the same effect through a different mechanism: HumanEval's
`k` argument has no effect on the reported number (class 2), and Okareo's `temperature=0` is
discarded on read (class 2).

**Affected libraries: 1.**

**How to detect it.** For every constructor and function parameter, grep for a use beyond the
signature; a parameter read zero times is the finding. The test shape: pass a non-default
value and assert observable behaviour changes. `git log` on the file often names the moment
the wiring was lost.

### 12. A merge or copy that drops or corrupts usage

**Definition.** Code that merges, accumulates or copies usage objects encodes its own
assumption about the provider's stream semantics or the model's field list, and silently
loses or inflates counters when the assumption is wrong.

**Mechanism.** Three variants. A spread merge where absent keys exist with value `undefined`
overwrites the counters captured at `message_start`, so after any streamed call the input side
of the accounting is not wrong, it is gone. A handler treats `message_delta.output_tokens`,
which Anthropic sends as the running total, as an increment, and adds it to the count it
already holds. A merge function rebuilds metadata from a hand-maintained field list, so every
field added to the model after the list was written is dropped, on the default path.

**Findings.**

- [`openllmetry-4377-double-counted-tokens.md`](findings/openllmetry-4377-double-counted-tokens.md), [traceloop/openllmetry#4377](https://github.com/traceloop/openllmetry/pull/4377), open. 174 reported against a true 171 on the repo's own cassette; the vendor SDK assigns where this code adds.
- [`cohere-784-embed-meta-dropped.md`](findings/cohere-784-embed-meta-dropped.md), [cohere-ai/cohere-python#784](https://github.com/cohere-ai/cohere-python/pull/784), open. `meta.tokens` comes back `None` on the default batching path and populated with `batching=False`; nothing in the signature suggests a batching flag should change which usage numbers come back.
- Cross-listed from class 1: [`mcp-use-2127-streamed-usage-erased.md`](findings/mcp-use-2127-streamed-usage-erased.md), [mcp-use/mcp-use#2127](https://github.com/mcp-use/mcp-use/pull/2127), open, counted in class 1. The end-to-end test reports `totalTokens: undefined` on the base commit. Their review then surfaced a third copy of the same arithmetic that I had missed, which is written up honestly in the finding.

**Affected libraries: 3, one of them via the cross-listing.**

**How to detect it.** Replay a recorded SSE cassette through both the library's accumulator
and the vendor SDK's, and diff the result; the OpenLLMetry number came straight from the
repo's own existing cassette. Assert the output value itself, not only the
`input + output == total` identity, which held while the output was wrong. For hand-copied
field lists, drive the assertions off the model's own fields, so adding a field without
touching the merge fails immediately; that is what the cohere test does.

### 13. The same silence, somewhere other than a number

**Definition.** The identical failure mode wearing different clothes: a code path produces
something well-formed and plausible, hands it to a caller with no way to tell, and never says
a word. The artifact is not a float, it is a message, a trace tree, or a file.

**Findings.**

- [`litellm-34769-ollama-tool-calls.md`](findings/litellm-34769-ollama-tool-calls.md), [BerriAI/litellm#34769](https://github.com/BerriAI/litellm/pull/34769), open. The `ollama/` route drops every tool call when `stream=true`: HTTP 200, `finish_reason` of `"stop"`, and the raw JSON in front of the customer. A cancel-and-refund request produces no cancellation and no refund. One version of the fix passed unit tests and broke against a real ollama, caught only by running it live.
- [`judgeval-769-foreign-parent-span.md`](findings/judgeval-769-foreign-parent-span.md), [JudgmentLabs/judgeval#769](https://github.com/JudgmentLabs/judgeval/pull/769), open. Whatever span the host application left current becomes the parent of the next Judgment span, silently rerooting it onto a foreign trace. For a tracing library this is the hardest failure to notice, because the only artifact is a shape in a UI that looks like a shape.
- [`cohere-785-csv-blank-rows.md`](findings/cohere-785-csv-blank-rows.md), [cohere-ai/cohere-python#785](https://github.com/cohere-ai/cohere-python/pull/785), open. `save_csv` writes `\r\r\n` row terminators on Windows; Python's own csv reader copes, so the round trip looks fine and the damage only shows downstream, in Excel and in `pandas.read_csv`.

**Affected libraries: 3.**

**How to detect it.** Parity tests between the streamed and non-streamed paths: the same
request with `stream=true` and `stream=false` must produce the same `tool_calls`. For file
output, assert exact bytes rather than parsed content, since the parser's tolerance is what
hides the defect. For tracing, start a span while a foreign span is current and assert its
parent is `None`.

### Outside the taxonomy

[`litellm-34770-banner-encoding.md`](findings/litellm-34770-banner-encoding.md),
[BerriAI/litellm#34770](https://github.com/BerriAI/litellm/pull/34770), open: the proxy fails
to start on a console that cannot encode its decorative banner. Its own write-up says it is
included for completeness rather than for the argument, and it is not counted in any class.

And one **negative result**:
[`not-a-bug-litellm-30135.md`](findings/not-a-bug-litellm-30135.md), a reported bug chased,
reproduced, and shown not to be a bug at all, followed by a 2026-08-12 caveat that the
reproduction itself needs re-running and stands as an open question rather than a result. It
is here at the same length as the real ones, because a record that only ever confirms is not
evidence of a working method. Chasing it down is what surfaced the real DashScope defect in
class 9.

## The obvious fix is often wrong in the same way

This recurs often enough across classes to state once. The proposed fix on the Helicone issue
fixes the reported symptom and leaves Bedrock broken, because the threshold basis keys off the
model's author, not the serving provider. The fix the sycophancy issue proposes reports a
different wrong number, 0.15 against a correct 0.2727. The naive BFCL fix clears 61 cases and
silently breaks 1281. My own closed LlamaIndex patch would have double-counted by exactly 2x
on the path it was most likely to run on, which is documented in the finding rather than
hidden. The reason the trap exists is the same reason the bugs exist: nothing in the system
can tell you the number is wrong. You have to derive it from the provider's billing rules or
the benchmark's definition and check.

## Prevalence

Counts are findings in `findings/` per primary class; statuses are PR states from the GitHub
API, 2026-08-15. The mapping behind this table is [`taxonomy.json`](taxonomy.json).

| # | Class | Findings | Merged | Open | Closed unmerged |
|---|---|---|---|---|---|
| 1 | Cache-token exclusion | 4 | 1 | 1 | 2 |
| 1a | ...family members without write-ups (Pipecat, Haystack) | 2 | 2 | 0 | 0 |
| 2 | A guard that filters a legal value | 3 | 0 | 3 | 0 |
| 3 | Silent-zero metrics | 3 | 1 | 2 | 0 |
| 4 | Denominator does not match what was counted | 2 | 0 | 2 | 0 |
| 5 | Fix lands on some twins and not others | 4 | 1 | 1 | 2 |
| 6 | Schema default scored as disagreement | 1 | 1 | 0 | 0 |
| 7 | Truncation scored as the answer (no write-up, PR only) | 1 | 1 | 0 | 0 |
| 8 | Aggregate written where the per-sample value belongs | 1 | 0 | 1 | 0 |
| 9 | Pricing tiers unreachable or mis-modeled | 3 | 0 | 2 | 1 |
| 10 | Missing price data, cost silently dropped | 2 | 1 | 1 | 0 |
| 11 | Config accepted and silently ignored | 1 | 0 | 1 | 0 |
| 12 | A merge or copy that drops or corrupts usage | 2 | 0 | 2 | 0 |
| 13 | The same silence, somewhere other than a number | 3 | 0 | 3 | 0 |
| | Outside the taxonomy | 1 | 0 | 1 | 0 |
| | Negative result (no PR) | 1 | | | |

Each finding is counted once, in its primary class; `mcp-use#2127` also carries the class 12
streaming defect and is cross-listed there without being counted twice. The write-up rows sum
to 31: 29 defects in classes 1 through 13, one outside the taxonomy, one negative result.

The index below has 32 rows: 30 finding files with pull requests, one merged PR without a
write-up (`inspect_evals#2097`), and one negative result with no PR. Its 31 pull requests
split 6 merged, 20 open, 5 closed unmerged. The corpus-wide totals, 52 substantive PRs, 9
merged, 34 open, 9 closed unmerged, include PRs outside `findings/`; the full unfiltered list
is
[`is:pr author:arthi-arumugam-git`](https://github.com/search?q=is%3Apr+author%3Aarthi-arumugam-git&type=pullrequests).

## The findings

Of the nine merged corpus-wide, `inspect_evals#2036`, `#2042` and `#2097` went in at the UK AI
Security Institute and shipped in Release v0.17.0 on 2026-08-14, `pipecat#5163` at Daily about
four hours after it opened, `livekit/agents#6663` was approved and merged by LiveKit's
co-founder, `supervision#2468` and `inference#2745` at Roboflow, the first after a review that
caught a real hole in my first attempt and the second approved by two maintainers,
`haystack-core-integrations#3717` at deepset after a round of requested changes, and
`genai-prices#520` at Pydantic. On the first two inspect_evals fixes the maintainer pushed
commits before merging, so those merged diffs are not purely mine.

Nine were closed unmerged, and four of those were closed as duplicates of a fix that landed
instead: `phoenix#14761` (superseded by @Anuj7411's own PR, which also closed the issue mine
claimed to close), `inference#2748` (by #2747, opened hours earlier), `crewAI#6838` (by a
maintainer's own #6844) and `respan#339` (by #344). The rest: `verifiers#2176` closed in a
triage sweep, `llama_index#22548` where the callback system is deprecated, `deepeval#2995`
self-closed as obsolete, `superset#33377` on a botched rebase, and `inspect_scout#9` which I
closed myself once I found upstream had shipped the fix in June.

| Status | Class | Where | Finding | PR |
|---|---|---|---|---|
| **merged** | 6 | `UKGovernmentBEIS/inspect_evals` | [BFCL scores a schema default as a disagreement](findings/inspect-evals-2042-bfcl-optional-defaults.md) | [#2042](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2042) |
| **merged** | 3 | `UKGovernmentBEIS/inspect_evals` | [sycophancy's confidence and apologize_rate report 0.0 on every run](findings/inspect-evals-2036-sycophancy-metrics.md) | [#2036](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2036) |
| **merged** | 7 | `UKGovernmentBEIS/inspect_evals` | truncated reasoning scored as the answer (no write-up) | [#2097](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2097) |
| **merged** | 1 | `livekit/agents` | [Bedrock prompt_tokens excludes cached tokens](findings/livekit-6663-bedrock-cached-tokens.md) | [#6663](https://github.com/livekit/agents/pull/6663) |
| **merged** | 5 | `roboflow/supervision` | [Recall tracks a different class set than Precision and F1](findings/supervision-2468-recall-prediction-only-classes.md) | [#2468](https://github.com/roboflow/supervision/pull/2468) |
| **merged** | 10 | `pydantic/genai-prices` | [Palmyra X4 and X5 on Bedrock resolve no price at all](findings/genai-prices-520-palmyra-bedrock.md) | [#520](https://github.com/pydantic/genai-prices/pull/520) |
| open | 3 | `UKGovernmentBEIS/inspect_evals` | [a run where nothing parsed reports StereoSet's ideal score](findings/inspect-evals-2123-stereoset-unscorable.md) | [#2123](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2123) |
| open | 1, 12 | `mcp-use/mcp-use` | [the streamed total was not wrong, it was gone](findings/mcp-use-2127-streamed-usage-erased.md) | [#2127](https://github.com/mcp-use/mcp-use/pull/2127) |
| open | 2 | `confident-ai/deepeval` | [HumanEval collapses pass@k into pass@n](findings/deepeval-2967-humaneval-pass-at-k.md) | [#2967](https://github.com/confident-ai/deepeval/pull/2967) |
| open | 3 | `confident-ai/deepeval` | [ToolUseMetric scores 0 when no tool was needed](findings/deepeval-2968-tool-use-metric.md) | [#2968](https://github.com/confident-ai/deepeval/pull/2968) |
| open | 4 | `confident-ai/deepeval` | [benchmark denominators don't match what was scored](findings/deepeval-2966-benchmark-denominators.md) | [#2966](https://github.com/confident-ai/deepeval/pull/2966) |
| open | 5 | `confident-ai/deepeval` | [ConversationalGEval ignores the rubric range](findings/deepeval-2965-conversational-geval-rubric.md) | [#2965](https://github.com/confident-ai/deepeval/pull/2965) |
| open | 8 | `voxel51/fiftyone` | [every sample's Dice score is the running dataset average](findings/fiftyone-8195-cumulative-dice.md) | [#8195](https://github.com/voxel51/fiftyone/pull/8195) |
| open | 9 | `Helicone/helicone` | [higher pricing tiers unreachable on 24 endpoints](findings/helicone-5737-unreachable-tiers.md) | [#5737](https://github.com/Helicone/helicone/pull/5737) |
| open | 9 | `BerriAI/litellm` | [DashScope tiers each token category independently](findings/litellm-34760-dashscope-tiers.md) | [#34760](https://github.com/BerriAI/litellm/pull/34760) |
| open | 13 | `BerriAI/litellm` | [ollama/ drops every tool call when stream=true](findings/litellm-34769-ollama-tool-calls.md) | [#34769](https://github.com/BerriAI/litellm/pull/34769) |
| open | out | `BerriAI/litellm` | [proxy won't start on a console that can't encode the banner](findings/litellm-34770-banner-encoding.md) | [#34770](https://github.com/BerriAI/litellm/pull/34770) |
| open | 13 | `JudgmentLabs/judgeval` | [a foreign global OTel span is adopted as parent](findings/judgeval-769-foreign-parent-span.md) | [#769](https://github.com/JudgmentLabs/judgeval/pull/769) |
| open | 2 | `langfuse/langfuse-python` | [cost dropped when usage is a dict or cost is an int](findings/langfuse-1781-dropped-cost.md) | [#1781](https://github.com/langfuse/langfuse-python/pull/1781) |
| open | 10 | `pydantic/logfire` | [AnthropicBedrock calls carry tokens but never a cost](findings/logfire-2162-bedrock-cost-dropped.md) | [#2162](https://github.com/pydantic/logfire/pull/2162) |
| open | 2 | `okareo-ai/okareo-python-sdk` | [temperature=0 overwritten by the class default](findings/okareo-260-temperature-zero.md) | [#260](https://github.com/okareo-ai/okareo-python-sdk/pull/260) |
| open | 11 | `okareo-ai/okareo-python-sdk` | [timeout accepted and never passed to the client](findings/okareo-261-timeout-ignored.md) | [#261](https://github.com/okareo-ai/okareo-python-sdk/pull/261) |
| open | 12 | `traceloop/openllmetry` | [streamed output tokens double-counted](findings/openllmetry-4377-double-counted-tokens.md) | [#4377](https://github.com/traceloop/openllmetry/pull/4377) |
| open | 12 | `cohere-ai/cohere-python` | [batched embed drops meta.tokens and image billed units](findings/cohere-784-embed-meta-dropped.md) | [#784](https://github.com/cohere-ai/cohere-python/pull/784) |
| open | 13 | `cohere-ai/cohere-python` | [save_csv writes a blank row between every record on Windows](findings/cohere-785-csv-blank-rows.md) | [#785](https://github.com/cohere-ai/cohere-python/pull/785) |
| open | 4 | `vellum-ai/vellum-python-sdks` | [mean metric divides by the unfiltered length](findings/vellum-3741-mean-denominator.md) | [#3741](https://github.com/vellum-ai/vellum-python-sdks/pull/3741) |
| closed | 1 | `crewAIInc/crewAI` | [150 tokens reported for a call that billed 350](findings/crewai-6838-anthropic-cached-tokens.md) | [#6838](https://github.com/crewAIInc/crewAI/pull/6838) |
| closed | 1 | `run-llama/llama_index` | [3 prompt tokens reported for a call that billed 21,503](findings/llamaindex-22548-anthropic-cache-tokens.md) | [#22548](https://github.com/run-llama/llama_index/pull/22548) |
| closed | 5 | `roboflow/inference` | [the weights proxy double-wraps and drops the gateway base path](findings/inference-2748-gateway-proxy-parity.md) | [#2748](https://github.com/roboflow/inference/pull/2748) |
| closed | 5 | `respanai/respan` | [Gemini thinking tokens land on no attribute at all](findings/respan-339-gemini-thinking-tokens.md) | [#339](https://github.com/respanai/respan/pull/339) |
| closed | 9 | `Arize-ai/phoenix` | [LiteLLM tier rates never reach the cost manifest](findings/phoenix-14761-tier-rates.md) | [#14761](https://github.com/Arize-ai/phoenix/pull/14761) |
| n/a | neg | `BerriAI/litellm` | [not a bug: issue #30135, investigated and not filed](findings/not-a-bug-litellm-30135.md) | none |

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

If you maintain one of these and I've got something wrong, open an issue here or comment on
the PR and I'll fix or withdraw it.

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

## Limitations

The sample is not random. I picked these libraries because they are the ones I use, and I read
them looking for exactly this defect class, so nothing here supports a claim about how common
these defects are in libraries I did not read, or relative to defect classes I was not looking
for. 52 pull requests across 34 organisations is less impressive than it sounds: they are one
bug pattern found repeatedly, not 52 independent investigations. Once you know the shapes
above, finding the next one is grep and forty minutes.

I make no causal claim about why the defects cluster where they do. I tried twice to measure
test coverage over metric code and withdrew both attempts, as described at the top; the
taxonomy classifies what the defects are, not what caused them. Where a finding's own evidence
weakened under re-audit, the finding says so in place: the LlamaIndex fix that would have
double-counted, and the LiteLLM negative result whose reproduction is an open question. The
classes themselves are a reading of the findings, and a different reader could cut them
differently; `taxonomy.json` exists so that disagreement can be concrete.

## Where this came from

I kept wanting to see a number change when nothing else did, so I built
[whatbroke](https://github.com/arthi-arumugam-git/whatbroke), a CLI that diffs an agent's
behaviour between two runs of the same task: tool calls, arguments, costs and outputs.

Arthi Arumugam · [github.com/arthi-arumugam-git](https://github.com/arthi-arumugam-git)
