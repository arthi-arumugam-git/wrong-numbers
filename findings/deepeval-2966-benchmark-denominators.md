# Benchmark accuracy denominators don't match what was scored

**Library:** confident-ai/deepeval · **PR:** [#2966](https://github.com/confident-ai/deepeval/pull/2966)
· **Status:** open, unreviewed by a human maintainer as of 2026-08-02

Two benchmarks divide by a denominator that isn't the set of goldens they actually scored.
Neither raises.

## EquityMedQA

Scores the first 10 goldens of each task:

```python
for golden in tqdm(goldens[:10], desc=f"Processing {task.value}"):
```

and sets the denominator from the full task:

```python
task_total_predictions = len(goldens)
overall_total_predictions += len(goldens)
```

The reported accuracy is scaled by `10 / len(goldens)`.

**The number:** a model that answers every scored golden correctly on a 40-golden task reports
**0.25**. On `fbrt_llm_661_sampled` (661 goldens) a perfect run reports **0.015**. Only tasks
with 10 or fewer goldens are correct today.

The `[:10]` cap was also hard-coded, so there was no way to run the full benchmark at all.

## GSM8K

Divides by the requested `n_problems` rather than the goldens actually loaded:

```python
overall_total_predictions = self.n_problems
goldens = self.load_benchmark_dataset()[: self.n_problems]
```

and unlike BoolQ, LAMBADA, Winogrande and ARC it has no bound on `n_problems`.

**The number:** `GSM8K(n_problems=5000)` is accepted, runs the 1319 problems that exist, and
deflates accuracy by `1319/5000`. A perfect model reports **0.264**.

## Behaviour change

The EquityMedQA cap becomes `n_problems_per_task`, defaulting to 10, so an existing run scores
exactly the same goldens as before and only the denominator changes. For GSM8K with
`n_problems <= 1319` the two denominators are equal, so correct runs are unaffected.

## Reproduce

- Source: `deepeval/benchmarks/equity_med_qa/equity_med_qa.py`, `deepeval/benchmarks/gsm8k/gsm8k.py`
- Test: `tests/test_benchmarks/test_benchmark_accuracy_denominator.py`, 5 of 8 fail on `main`

```bash
gh pr checkout 2966 --repo confident-ai/deepeval
git checkout origin/main -- deepeval/benchmarks/equity_med_qa/equity_med_qa.py deepeval/benchmarks/gsm8k/gsm8k.py
python -m pytest tests/test_benchmarks/test_benchmark_accuracy_denominator.py -q
```

The dataset and predictions are scripted fakes: no model, network or API key.
