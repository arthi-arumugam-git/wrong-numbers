# `save_csv` writes a blank row between every record on Windows

**Library:** cohere-ai/cohere-python · **PR:** [#785](https://github.com/cohere-ai/cohere-python/pull/785)
· **Status:** open 

## What's wrong

`save_dataset(format="csv")` opens the file with `open(filepath, "w")` and hands it to
`csv.DictWriter`. `DictWriter` terminates every row with `\r\n` itself, and on Windows a text
stream then translates that `\n` into `\r\n` as well, so every row ends up terminated with
`\r\r\n`.

```python
>>> save_csv(dataset, "out.csv")
>>> open("out.csv", "rb").read()
b'text,label\r\r\nhello,a\r\r\ngoodbye,b\r\r\n'
>>> open("out.csv").readlines()
['text,label\n', '\n', 'hello,a\n', '\n', 'goodbye,b\n', '\n']
```

## Why it survives

Python's own `csv` reader copes with it, so a round trip back through the SDK looks fine and the
damage only shows up downstream. Excel renders a blank row after every record, and
`pandas.read_csv` gives back rows of `NaN` unless `skip_blank_lines` is set.

The csv docs call this out directly: the file has to be opened with `newline=""`. That is the whole
change. `save_avro` already opens in binary so it was never affected; `save_jsonl` writes its own
separator and is a different question.

## The awkward part, stated openly

The bug only reproduces on a platform whose text streams translate newlines. **On Linux the
unfixed code writes correct bytes**, so any test that inspects the file passes with or without the
fix, and Linux CI would be guarding nothing.

So there are three tests. Two inspect the file and assert exact bytes rather than counting blank
rows, since that states the real contract; they fail on Windows without the change. The third
asserts the `open` call itself:

```python
self.assertEqual(opened.call_args.kwargs.get("newline"), "")
```

That one fails on every platform, so Linux CI does catch it if the argument is ever dropped again.
Coupling a test to a call shape isn't something to reach for casually, and the test carries a
comment saying why.

## Reproduce

- Source: `src/cohere/utils.py`
- Test: `tests/test_save_dataset.py`, 3 cases

```bash
gh pr checkout 785 --repo cohere-ai/cohere-python
git checkout origin/main -- src/cohere/utils.py
python -m pytest tests/test_save_dataset.py -q
```

On Linux, expect only the `open`-call test to fail. The byte-level tests need Windows.

Only `src/cohere/utils.py` and `tests/` are touched, both listed in `.fernignore`. `mypy .` clean
across 342 files.
