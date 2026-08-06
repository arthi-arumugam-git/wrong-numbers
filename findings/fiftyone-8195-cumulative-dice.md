# Every sample's Dice score is the running dataset average

`voxel51/fiftyone` · [#8195](https://github.com/voxel51/fiftyone/pull/8195) ·
`fiftyone/utils/eval/segmentation.py`

## The number

Two samples, a perfect match followed by a total mismatch:

| | reported | correct |
|---|---|---|
| perfect sample | 1.0 | 1.0 |
| mismatched sample | **0.5** | 0.0 |

0.5 is exactly the Dice of the two confusion matrices summed, which is what makes the cause
unambiguous rather than inferred.

## The code

```python
confusion_matrix += sample_conf_mat          # dataset-wide accumulator

if save:
    sacc, spre, srec = _compute_accuracy_precision_recall(
        sample_conf_mat, values, average     # this sample
    )
    sample[acc_field] = sacc
    sample[pre_field] = spre
    sample[rec_field] = srec
    if compute_dice:
        sample[dice_field] = _compute_dice_score(confusion_matrix)   # the accumulator
```

Accuracy, precision and recall on the three lines directly above use `sample_conf_mat`. The
frame-level Dice eleven lines earlier uses `image_conf_mat`. Only the sample-level Dice reaches
for the accumulator, which was incremented on the line before and holds every sample seen so
far.

So `<eval_key>_dice` is the running cumulative Dice. It drifts toward the dataset mean as
evaluation proceeds, and it changes if the samples are iterated in a different order.

## Why it survived since 2023

`_compute_dice_score` names its own parameter `confusion_matrix`, the same name as the
accumulator at the call site, so `_compute_dice_score(confusion_matrix)` reads as correct.

It is also invisible in the two cases anyone checks first. With a single sample the accumulator
equals that sample's matrix. With the offending sample evaluated first, it is right too. The
error only appears from the second sample onward.

## The fix

Pass `sample_conf_mat`, matching the three sibling metrics. One line.

## Test

Two, both failing before the change. The second is the one worth keeping: it evaluates the same
data forward and reversed and asserts each sample keeps its score. A cumulative value is order
dependent, so it fails on the old behaviour, and order dependence is precisely why this was not
noticed.
