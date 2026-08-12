# Proxy won't start on a console that can't encode the banner

**Library:** BerriAI/litellm · **PR:** [#34770](https://github.com/BerriAI/litellm/pull/34770)
· **Status:** open · Automated review: 5/5

The smallest item in the set, and included for completeness rather than for the argument.

## What's wrong

The proxy prints a decorative startup banner. On a console whose encoding can't represent the
characters in it, Windows `cp1252` being the common case, the print raises, and the proxy fails
to start.

A cosmetic line takes down the process before it serves anything.

## Why it's here at all

It's the same category as the rest only in the loosest sense: an unexamined assumption about the
environment, in a path nobody thought could fail. It is not thesis material and shouldn't be read
as such.

## Reproduce

- Source: `litellm/proxy/common_utils/banner.py`
- Test: `tests/test_litellm/proxy/common_utils/test_banner.py`

```bash
gh pr checkout 34770 --repo BerriAI/litellm
git checkout origin/main -- litellm/proxy/common_utils/banner.py
python -m pytest tests/test_litellm/proxy/common_utils/test_banner.py -q
```

The test simulates the restricted-encoding stream, so it fails on any platform rather than only on
Windows.
