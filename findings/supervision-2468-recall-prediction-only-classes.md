# `Recall` tracks a different set of classes than `Precision` and `F1Score`

**Library:** roboflow/supervision · **Issue:** [#2467](https://github.com/roboflow/supervision/issues/2467)
· **PR:** [#2468](https://github.com/roboflow/supervision/pull/2468) · **Status:** open

## What's wrong

The three metrics return `matched_classes` and a `*_per_class` array. They read like parallel
outputs of one computation, and they are not.

[#2331](https://github.com/roboflow/supervision/pull/2331) taught `Precision` and `F1Score` to
track classes that appear only in predictions, since those predictions are false positives and
were not being counted. It changed `f1_score.py` and `precision.py`, added about eighty lines
of regression tests to each, updated the docstrings and wrote a changelog entry.

`recall.py` sits beside them, implements the same shape of computation, and was not changed.
The line #2331 replaced in `precision.py` is still at `recall.py:331`.

## The number

Ground truth contains only class 0. The model predicts class 0 correctly and also predicts a
class 1 that appears nowhere in the targets.

| metric | `matched_classes` | `*_per_class` shape | macro @ IoU 0.50 |
|---|---|---|---|
| precision | `[0 1]` | `(2, 10)` | 0.5 |
| f1 | `[0 1]` | | 0.5 |
| **recall** | **`[0]`** | **`(1, 10)`** | 1.0 |

Nothing raises. The obvious next line is the one that costs you:

```python
for cid, p, r in zip(pres.matched_classes,
                     pres.precision_per_class[:, 0],
                     rec.recall_per_class[:, 0]):
    ...
```

`zip` stops at the shortest, so you get one row where precision found two classes, and the
hallucinated class disappears from the table with no error. Had the arrays been the same
length but a different membership, the values would have been attributed to the wrong classes
instead, which is worse, because then the table looks complete.

## Why this was filed as a question before a patch

Recall for a class with no ground-truth instances is undefined rather than obviously zero, and
making `Recall` match its siblings moves a number the project publishes. A confident patch
that changes a published metric is a good way to be confidently wrong, so #2467 laid out both
options and asked.

Two things in the repository answered it, which is the point worth keeping:

- `tests/metrics/test_precision.py` cites scikit-learn as the standard for a related decision.
  scikit-learn infers labels from the union of `y_true` and `y_pred`, gives a prediction-only
  label a recall of `0.0`, and includes it in the macro average. Checked by running it:
  macro recall `0.1667`, not `0.3333`.
- `recall.py` had already received #2331's zero-support guard for `WEIGHTED`, whose comment
  refers to *"only false-positive classes"*. **That state could not arise in `recall.py`**,
  because its class list came from the ground truth alone. The guard was copied across. The
  change that gave it meaning was not.

So the intent to treat the three alike was already in the file. Only half of it had landed.

## What moves

`MICRO` is unchanged: an absent class contributes no false negatives. `WEIGHTED` is unchanged:
its ground-truth support is zero, so its weight is zero. **`MACRO` moves**, for any evaluation
containing predictions of a class with no ground-truth instances, and the changelog entry
states that rather than burying it.

## Is anything else affected

`tests/metrics/` has a file per metric. Four cover the case where a class appears only in
predictions: `test_detection.py`, `test_f1_score.py`, `test_mean_average_recall.py`,
`test_precision.py`. One does not, and it is `test_recall.py`. That asymmetry is easier to
spot than the defect itself, and it is checkable in seconds.

Two candidates in the same module were chased and **not** filed:

- `detection.py:1624` guards the recall denominator with `+ eps` and leaves the precision
  denominator on the next line unguarded. It looks like the same shape and is not reachable:
  `true_positives + false_positives` is `cumsum(matches) + cumsum(1 - matches)`, the running
  prediction count, which starts at 1.
- `precision.py` and `recall.py` pass `out=np.zeros_like(true_positives)` to `np.divide` with
  no dtype, where `f1_score.py` passes `dtype=np.float64`. Harmless: the confusion matrix is
  allocated `float64`, so `zeros_like` is already float64.

## Reproduce

- Source: `src/supervision/metrics/recall.py`
- Tests: `tests/metrics/test_recall.py`

```bash
git clone -b develop https://github.com/roboflow/supervision.git && cd supervision
PYTHONPATH=src python -m pytest tests/metrics/test_recall.py -q
```

Four new cases fail before the change: the three averaging methods against a class predicted
but never in the targets, and `test_tracked_classes_match_precision_and_f1`, which asserts the
three metrics agree on the class set and per-class row count for the same data. That is the
invariant that was actually broken, so it gets a test of its own.

Whole metrics suite: **280 passing, up from 276, with no existing test modified.**
