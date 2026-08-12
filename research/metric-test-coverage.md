# The metrics are the least-tested code in the eval stack

Measured with each framework's **own** registration marker, so "this is a metric" is the
framework's judgement and not mine. A metric counts as touched if **either** its function name
**or** the name it is registered under appears anywhere in any test file.

| Framework | Registered metrics | Never touched by any test | Rate |
|---|---:|---:|---:|
| [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) (EleutherAI) — `@register_metric` / `@register_aggregation` | 23 | 14 | **61%** |
| [inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals) (UK AI Security Institute) — `@metric` | 136 | 44 | **32%** |

Untested in `lm-evaluation-harness`: `acc_all`, `acc_bytes`, `bits_per_byte`, `brier_score`,
`bypass`, `byte_perplexity`, `chrf`, `likelihood`, `matthews_corrcoef`, `mcc`, `nanmean`,
`ter`, `weighted_perplexity`, `word_perplexity`.

Reproduce:

```bash
python research/audit_metric_coverage.py path/to/repo
```

## Why this is the finding and the pull requests are the evidence

The rest of this repository is a catalogue: defects in shipped libraries, each one a number
that comes out wrong while nothing raises. Read as a catalogue it invites the obvious
objection, that anyone who looks hard enough at any codebase will find something.

This is the answer. The defects are not evenly distributed. They concentrate in metric
functions, and metric functions are where the tests are not. That is a mechanism, and it
predicts where the next one will be.

## Why metrics specifically

1. **A metric returns a float, so nothing type-checks it.** A parser that breaks returns the
   wrong type and something downstream complains. A metric that breaks returns `0.15` where
   the truth was `0.2727`, and `0.15` is a perfectly ordinary number.
2. **Failure is indistinguishable from a result.** In
   [`stereoset`](../findings/inspect-evals-2123-stereoset-unscorable.md) a run where every
   answer failed to parse reported 50, which is that benchmark's *ideal* score. There is no
   exception to catch, because nothing went wrong from the code's point of view.
3. **The metric is written last and is the least interesting part.** The eval is the
   contribution; the aggregation is plumbing at the end of the file.
4. **Testing a metric means asserting on arithmetic, which feels redundant** right up until
   the denominator is the wrong set.

## The taxonomy

| Shape | What goes wrong | Instances |
|---|---|---|
| **Wrong denominator** | The average divides by a different set than the one it summed | `inspect_evals#2036`, `vellum#3741`, `deepeval#2966` |
| **Silent exclusion** | Failed samples are filtered out, shrinking the denominator without saying so | `inspect_evals#2123`, `autoevals#210` |
| **Sentinel collapse** | An "unknown" value is coerced to a real one, usually `NaN` to `0` | `RE-Bench#43`, `inspect_evals#2123` |
| **Truncated basis** | The score is computed against the model's own output rather than ground truth | `inspect_evals#2060`, `inspect_evals#2097` |
| **Partial propagation** | A fix lands on some of a set of near-identical files and not the rest | `supervision#2468`, `roboflow/inference#2745` |

The first three are the same failure underneath: **the code decides what to do with a sample
it could not score, and it decides silently.**

## Method, and what it does not show

Both figures use the framework's own decorator to identify a metric, and count a metric as
touched if either its function name or its registered name appears anywhere in any test file.
That is deliberately generous, so both figures are **lower bounds**: appearing in a test is not
the same as being asserted on.

**Only two frameworks are reported, and that is deliberate.** An earlier draft of this page
carried a five-framework table built on a path-and-name heuristic. It was wrong, in three
separate ways, and the corrections are worth stating because this repository has no business
publishing an unchecked number:

- One repository was scanned with a virtualenv inside it, so `site-packages` was counted as
  first-party code.
- The "anything in a `metrics/` directory" rule swept in Pydantic models, prompt classes and
  protocols. In `ragas`, roughly one flagged item in twelve was actually a metric.
- Metrics registered under a name distinct from their function name were counted as untested
  when a test exercised them through the registry. Correcting this alone moved
  `lm-evaluation-harness` from 87% to 61%.

`deepeval`, `ragas` and `autoevals` implement metrics as classes or through registries with no
single marker comparable to the two above, so no honest cross-framework rate covers them.
They are omitted rather than estimated.

What this does not show: that any given eval number is wrong. It shows that the code producing
them is unexercised, and that where anyone has looked, defects were there.

## What follows from it

1. **A metric with no test is an unverified claim.** These numbers appear in system cards,
   safety reports and regulatory submissions.
2. **Test the failure paths, not the happy path.** Every defect in this repository is correct
   on well-formed input. The bugs live in what happens to the sample that did not parse.
3. **Make "I could not score this" a value the metric has to handle.** Four of the five shapes
   disappear if unscorable samples are a distinct state rather than a zero.
4. **Never let an empty denominator return a number in the metric's own scale.** `0.0` became
   50 in `stereoset`, and 50 was the best possible result.
