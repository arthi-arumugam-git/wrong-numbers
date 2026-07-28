# HumanEval collapses pass@k into pass@n

**Library:** confident-ai/deepeval · **PR:** [#2967](https://github.com/confident-ai/deepeval/pull/2967)
· **Status:** open, unreviewed as of 2026-07-28

## What's wrong

```python
prediction, score = self.predict(model, task, golden, k).values()
if score:
    task_correct = 1
    overall_correct_predictions += 1
```

`score` is pass@k — a probability in `[0, 1]`, not a flag. `Scorer.pass_at_k(n, c, k)` returns
a non-zero value whenever at least one of the `n` samples passes, so `if score:` counts the task
as a full pass. That is pass@n regardless of the `k` that was asked for.

The `k` argument to `evaluate()` therefore has no effect on the reported number.

## The number

At the default `n=200, k=1`, a task where 1 of 200 samples passes has a true pass@1 of **0.005**
and is reported as **1.0**.

A model that stumbles onto each solution once in two hundred attempts scores 100% on HumanEval.

## Behaviour change

Any run at `k < n` now reports a different number. `k == n` is unchanged, and that invariant is
pinned by a test.

## Reproduce

- Source: `deepeval/benchmarks/human_eval/human_eval.py`
- Test: `tests/test_benchmarks/test_human_eval_pass_at_k.py`

```bash
gh pr checkout 2967 --repo confident-ai/deepeval
git checkout origin/main -- deepeval/benchmarks/human_eval/human_eval.py
python -m pytest tests/test_benchmarks/test_human_eval_pass_at_k.py -q
```

No model, network or API key required — the predictions are scripted.
