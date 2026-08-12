# ToolUseMetric scores 0 when no tool was needed

**Library:** confident-ai/deepeval · **PR:** [#2968](https://github.com/confident-ai/deepeval/pull/2968)
· **Status:** open 

## What's wrong

Argument correctness is only scored for interactions that actually called a tool:

```python
argument_correctness_scores = [
    self._get_argument_correctness_score(...)
    for user_and_tools in user_input_and_tools
    if user_and_tools.tools_used
]
```

When no turn calls a tool, that list is empty. `_calculate_score` still averages it (a sum of 0
over a divisor forced to 1) and folds the resulting `0.0` into the `min()`:

```python
argument_correctness_score_divisor = (
    len(argument_correctness_scores)
    if len(argument_correctness_scores) > 0
    else 1
)
argument_correctness_score = arguments_scores_sum / argument_correctness_score_divisor
score = min(tools_selction_score, argument_correctness_score)
```

## The number

A conversation where the model correctly answered **without needing any tool** scores **0**,
whatever the tool selection score says. That is the same score a model gets for picking every
tool wrong.

Any multi-turn suite mixing tool-requiring and conversational turns has its conversational turns
scored 0 and the aggregate dragged down, with no error, and a reason string that reads as if
tool use failed.

## The fix, and the objection it anticipates

When there are no argument correctness scores, use the tool selection score alone. Whether a tool
*should* have been called is already judged by the tool selection score, so a model that should
have called one and didn't still scores low. The fallback doesn't mask it, and a test pins that
case specifically.

Behaviour is unchanged whenever any tool was called: the same `min()` of the same two averages.

## Reproduce

- Source: `deepeval/metrics/tool_use/tool_use.py`
- Test: `tests/test_metrics/test_tool_use_metric_score.py`, 5 of 9 fail on `main`

```bash
gh pr checkout 2968 --repo confident-ai/deepeval
git checkout origin/main -- deepeval/metrics/tool_use/tool_use.py
python -m pytest tests/test_metrics/test_tool_use_metric_score.py -q
```

`_calculate_score` is called directly with scripted score lists and `__init__` is bypassed, so no
model, network or API key is needed. (The pre-existing `test_tool_use_metric.py` is skipped
without `OPENAI_API_KEY` and asserts no values.)
