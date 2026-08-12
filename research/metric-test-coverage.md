# I claimed eval metrics are untested. I measured it properly and I was wrong.

**Retracted:** "58% of metric definitions across five evaluation frameworks are never tested,"
and its successor "32% in `inspect_evals`." Both came from grepping test files for a metric's
name. That measures **naming convention**, not test coverage.

**What coverage instrumentation actually shows** for `UKGovernmentBEIS/inspect_evals`, running
the full suite (4,178 passed, 813 skipped, 10m46s) under `coverage.py` and asking which metric
functions executed:

| Population (framework's own decorator) | Never executed | Rate |
|---|---:|---:|
| `@metric` | 3 of 135 | **2%** |
| `@scorer` | 41 of 225 | 18% |
| **Total** | **44 of 360** | **12%** |

And 40 of those 44 are `build_scorer` clones in `theagentcompany` task directories, one per
task. The real figure for metric code proper is **2%**.

So the thesis this page was built on does not survive contact with a correct measurement.
Metrics in `inspect_evals` are exercised. They are reached through end-to-end task tests
without ever being named in a test file, which is precisely what the grep could not see.

## Why the wrong method was wrong

Reproduce either number with `research/audit_metric_coverage.py`. The grep mode is still in
there, marked as the weaker method, because the ways it failed are worth keeping:

- **Metrics exercised anonymously inside end-to-end tests scored as untested.** This dominates
  every other error and is why 32% became 12%.
- Metrics registered under a name different from their function name scored as untested when
  tests reached them through the registry. Fixing only this moved `lm-evaluation-harness` from
  87% to 61%.
- A metric whose only appearance in an entire test suite was inside a **code comment** scored
  as covered. Others appeared only as config strings in YAML-parsing tests, or in mocks that
  substituted a different aggregation.
- Fixture files full of metric names turned out to be **orphaned**, referenced by nothing. In
  `lm-evaluation-harness`, 340 `*-res.json` files under `tests/testdata/` contain metric names
  and no test loads any of them.
- A virtualenv inside one checkout put `site-packages` into the population.
- The first subset I sampled under coverage was four evals I had **personally added tests to**,
  which guaranteed a clean result. Choosing the sample is a research decision and I got it
  wrong before I got it right.

Coverage is not the last word either. **Executed is not asserted on**: a metric can run inside
a test that never checks its output. The only method that measures assertions is mutation
testing, which is the obvious next step and which I have not run.

## What survives

The defects. Every one below was reproduced against an installed package, with a test that
fails on `main`, and none of them depends on the coverage claim:

| Shape | What goes wrong | Instances |
|---|---|---|
| **Wrong denominator** | The average divides by a different set than the one it summed | `inspect_evals#2036`, `vellum#3741`, `deepeval#2966` |
| **Silent exclusion** | Failed samples filtered out, shrinking the denominator with nothing to say so | `inspect_evals#2123`, `autoevals#210` |
| **Sentinel collapse** | An unknown coerced to a real value, usually `NaN` to `0` | `RE-Bench#43`, `inspect_evals#2123` |
| **Truncated basis** | Scored against the model's own output rather than ground truth | `inspect_evals#2060`, `inspect_evals#2097` |
| **Partial propagation** | A fix lands on some of a set of near-identical files and not the rest | `supervision#2468`, `roboflow/inference#2745` |

The first three reduce to one thing: **the code decides what to do with a sample it could not
score, and it decides silently.**

The clearest instance is [`inspect_evals#2123`](https://github.com/UKGovernmentBEIS/inspect_evals/pull/2123).
`stereotype_score` dropped every zero before averaging, and four different outcomes produce a
zero, only one of which is a model judgement. When nothing survived, the empty branch returned
`0.0`, which the final expression turns into **50**: StereoSet's *ideal* score. A run where
every answer failed to parse was indistinguishable from a perfectly unbiased model.

That one had no test exercising it. Which is how this whole line of enquiry started, and it
remains true even though the population-level claim it inspired does not.

## Why this page still says all of that

A repository arguing that wrong numbers survive because nothing raises has no business quietly
deleting its own. The corrections are the argument, not an embarrassment to it. The number went
89, 87, 61, 57, 32, 12 across five methods in one day, and every move came from someone asking
whether the previous one was real.
