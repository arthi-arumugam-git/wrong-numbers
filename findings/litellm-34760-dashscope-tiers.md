# DashScope tiers each token category independently

**Library:** BerriAI/litellm · **PR:** [#34760](https://github.com/BerriAI/litellm/pull/34760)
· **Status:** open · Automated review: 5/5

## What's wrong

Alibaba Model Studio picks **one** pricing tier from the request's **total input size** and bills
every token at that tier.

LiteLLM's DashScope calculator instead ran each token category through a graduated,
income-tax-style helper, independently. So completion tokens selected their own tier starting
from zero, as did cached tokens, as did the prompt.

Two disagreements in one function: the wrong tier-selection model, and the wrong scope for it.

## The number

A 300k-input `qwen-flash` request logs at **$0.0246** against the **$0.079** actually charged.

**69% under.**

## What makes it survivable

The proxy's budget-reservation path already had the correct selector. Post-response spend simply
disagreed with the pre-request estimate, and nothing in the system compared the two.

## Reproduce

- Source: `litellm/llms/dashscope/cost_calculator.py`
- Test: `tests/test_litellm/llms/dashscope/test_dashscope_cost_calculator.py`

```bash
gh pr checkout 34760 --repo BerriAI/litellm
git checkout origin/main -- litellm/llms/dashscope/cost_calculator.py
python -m pytest tests/test_litellm/llms/dashscope/test_dashscope_cost_calculator.py -q
```

No credentials needed: the calculator is called directly with usage objects.

## Related

This is the defect that turned up while investigating
[#30135](not-a-bug-litellm-30135.md), which was **not** a bug. The expected figure in that report
assumed graduated pricing; chasing down why led here, where the graduated assumption was real and
wrong.
