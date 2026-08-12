# The metrics are the least-tested code in the eval stack

**1,237 metric and scorer definitions across five evaluation frameworks. 716 of them, 58%,
are never named in a single test file.**

| Framework | Metric/scorer definitions | Never named in a test | Rate |
|---|---:|---:|---:|
| [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) (EleutherAI) | 132 | 118 | **89%** |
| [ragas](https://github.com/explodinggradients/ragas) | 258 | 183 | 71% |
| [deepeval](https://github.com/confident-ai/deepeval) | 274 | 164 | 60% |
| [inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals) (UK AI Security Institute) | 566 | 248 | 44% |
| [autoevals](https://github.com/braintrustdata/autoevals) (Braintrust) | 7 | 3 | 43% |
| **Total** | **1,237** | **716** | **58%** |

Reproduce it:

```bash
python research/audit_metric_coverage.py path/to/repo [path/to/repo ...]
```

## Why this is the finding and the thirty pull requests are the evidence

The rest of this repository is a catalogue: thirty defects in shipped libraries, each one a
number that comes out wrong while nothing raises. Read as a catalogue it invites the obvious
objection, that anyone who looks hard enough at any codebase will find something.

This is the answer to that objection. The defects are not bad luck and they are not evenly
distributed through these codebases. They concentrate in metric functions, and metric
functions are where the tests are not.

That is a mechanism, not a complaint, and it predicts where the next one will be.

## Why metrics specifically

Four properties compound, and all four are structural rather than anyone's mistake:

1. **A metric returns a float, so nothing type-checks it.** A parser that breaks returns the
   wrong type and something downstream complains. A metric that breaks returns `0.15` where
   the truth was `0.2727`, and `0.15` is a completely ordinary number.
2. **Failure is indistinguishable from a result.** In
   [`stereoset`](../findings/inspect-evals-2123-stereoset-unscorable.md) a run where every
   single answer failed to parse reported 50, which is that benchmark's *ideal* score. In
   [`RE-Bench`](https://github.com/METR/RE-Bench/pull/43) a crashed run is coerced from `NaN`
   to `0`. There is no exception to catch because nothing went wrong from the code's point of
   view.
3. **The metric is written last and is the least interesting part.** The eval is the
   contribution; the aggregation is plumbing at the end of the file.
4. **Testing a metric means asserting on arithmetic, which feels redundant** right up until
   the denominator is the wrong set.

## The taxonomy

Every finding in this repository falls into one of five shapes. They are worth naming
because each one is checkable.

| Shape | What goes wrong | Instances |
|---|---|---|
| **Wrong denominator** | The average divides by a different set than the one it summed | `inspect_evals#2036`, `vellum#3741`, `deepeval#2966` |
| **Silent exclusion** | Failed samples are filtered out, shrinking the denominator without saying so | `inspect_evals#2123`, `autoevals#210` |
| **Sentinel collapse** | An "unknown" value is coerced to a real one, usually `NaN` to `0` | `RE-Bench#43`, `inspect_evals#2123` |
| **Truncated basis** | The score is computed against the model's own output rather than ground truth | `inspect_evals#2060`, `inspect_evals#2097` |
| **Partial propagation** | A fix lands on some of a set of near-identical files and not the rest | `supervision#2468`, `roboflow/inference#2745` |

The first three are all the same failure at bottom: **the code decides what to do with a
sample it could not score, and it decides silently.**

## Method, and what it does not show

The audit collects every top-level `def` or `class` that lives in a metric or scorer module,
or whose name marks it as producing a number, and asks whether that identifier appears
anywhere in any test file.

Step two is deliberately generous. Being named in a test is not the same as being tested: the
name might appear in an import, a fixture, or an end-to-end run that never asserts on the
number. **Every figure above is therefore a lower bound.**

The heuristic is approximate across frameworks, and a project that exercises its metrics only
through integration runs will look worse here than it deserves. As a check, the strict variant
on `inspect_evals`, counting only `@metric`-decorated functions, gives 42% against this
heuristic's 44%. Two independent definitions, two points apart.

What this does not show: that 58% of eval numbers are wrong. It shows that the code producing
them is unexercised, and that where anyone has looked, defects were there.

## What follows from it

1. **A metric with no test is an unverified claim.** These numbers appear in system cards,
   safety reports and regulatory submissions. The bar should be the same as for the code that
   runs the model.
2. **Test the failure paths, not the happy path.** Every defect above is correct on
   well-formed input. The bugs live in what happens to the sample that did not parse.
3. **Make "I could not score this" a value the metric has to handle.** Four of the five shapes
   disappear if unscorable samples are a distinct state rather than a zero.
4. **Never let an empty denominator return a number in the metric's own scale.** `0.0` became
   50 in `stereoset`, and 50 was the best possible result.
