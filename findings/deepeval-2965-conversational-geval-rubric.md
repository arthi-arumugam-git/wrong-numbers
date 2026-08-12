# ConversationalGEval ignores the rubric range

**Library:** confident-ai/deepeval · **PR:** [#2965](https://github.com/confident-ai/deepeval/pull/2965)
· **Status:** open 

## What's wrong

`ConversationalGEval` accepts a rubric but hard-codes 0-10 in both the prompt template and the
normalizer. The raw score is divided by 10 whatever range the rubric declares.

## The number

A perfect **5 on a 0-5 rubric** reports **0.5**.

`GEval`, given the identical rubric and the identical raw score, reports **1.0**. Same library,
two metrics, same input, different answer.

## Why it's worth its own entry

This isn't an oversight nobody caught. deepeval fixed exactly this bug in `g_eval.py` in
[PR #1915](https://github.com/confident-ai/deepeval/pull/1915), merged in August 2025. The fix
was correct. It just never reached the conversational variant, and the shared `get_score_range`
helper that fix introduced was sitting right there, unused by the twin.

A guard that is correct in one code path and never applied to its twin is one of the four shapes
this whole set keeps taking.

## Reproduce

- Source: `deepeval/metrics/conversational_g_eval/conversational_g_eval.py`, plus the prompt
  template and `templates.json`
- Test: `tests/test_metrics/test_conversational_g_eval_rubric_score_range.py`

```bash
gh pr checkout 2965 --repo confident-ai/deepeval
git checkout origin/main -- deepeval/metrics/conversational_g_eval/
python -m pytest tests/test_metrics/test_conversational_g_eval_rubric_score_range.py -q
```

Note this PR also touches `deepeval/templates/metrics/templates.json` and its TypeScript twin,
so the prompt text is part of the change, not only the normalizer.
