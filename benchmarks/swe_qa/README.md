# SWE-QA

576 question-answer pairs requiring repository-level code understanding.
Questions span cross-file reasoning, multi-hop dependency analysis, and
intention understanding.

Paper: https://arxiv.org/abs/2509.14635

## What it tests

Unlike SWE-bench (which tests editing), SWE-QA tests **comprehension
directly**. Questions include:

- "What happens when function X is called with argument Y?"
- "Which modules depend on this component?"
- "Why is this particular pattern used here?"

This is the benchmark most aligned with comprehend's core value
proposition: does structured codebase analysis produce better
understanding?

## Dataset

TODO: The SWE-QA dataset availability and download instructions should
be checked at the paper's associated repository. As of this writing,
the dataset may need to be obtained from the authors.

```python
# TODO: Update with actual dataset loading
# from datasets import load_dataset
# ds = load_dataset("swe-qa/SWE-QA", split="test")
```

## Running

```bash
python run_tasks.py --config ../../configs/baseline.json
python run_tasks.py --config ../../configs/comprehend.json
```

## Evaluation

Answers are evaluated by:
1. **Exact match** -- does the answer contain the key facts?
2. **LLM-as-judge** -- a separate Claude call scores the answer against
   the reference on a 1-5 scale for correctness and completeness.
