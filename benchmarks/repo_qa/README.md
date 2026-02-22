# RepoQA

500 code search tests across 50 repositories in 5 programming languages.
The task: given a natural-language description of a function, find the
matching function in the codebase.

Paper: https://arxiv.org/html/2406.06025v1

## What it tests

RepoQA's "Searching Needle Function" (SNF) task tests whether the model
genuinely understands code rather than pattern-matching. The model must:

1. Read the natural-language description
2. Search through the repository's code
3. Identify the specific function that matches

This tests the "search and understand" capability that comprehend's REPL
and subagent fan-out are designed to improve.

## Dataset

```python
# TODO: Check for official dataset availability
# The paper describes 500 tests from 50 repos in Python, Java, TypeScript,
# Rust, and C++. Check the paper's associated repository.
```

## Running

```bash
python run_tasks.py --config ../../configs/baseline.json
python run_tasks.py --config ../../configs/comprehend.json
```

## Evaluation

Pass/fail: does the returned function name and file path match the
ground truth? Partial credit for correct file but wrong function.
