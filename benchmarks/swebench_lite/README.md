# SWE-bench Lite

300 real GitHub issues from 12 Python repositories. Each task requires
understanding the codebase and producing a patch that resolves the issue.

## Dataset

```python
from datasets import load_dataset
ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
```

Each instance has:
- `instance_id` -- unique identifier (e.g., `astropy__astropy-12907`)
- `repo` -- repository name (e.g., `astropy/astropy`)
- `base_commit` -- git commit to check out before applying the patch
- `problem_statement` -- the GitHub issue text (this becomes the prompt)
- `patch` -- the gold-standard patch
- `test_patch` -- tests that verify the fix

## Running

```bash
# Curated subset (20-30 tasks, ~1 hour)
python run_tasks.py --config ../../configs/baseline.json
python run_tasks.py --config ../../configs/comprehend.json

# Full benchmark (300 tasks, ~10-20 hours)
python run_tasks.py --config ../../configs/baseline.json --all

# Evaluate with SWE-bench harness (requires Docker)
python evaluate.py results/baseline/predictions.jsonl
```

## Curated subset

`sample_tasks.json` contains 25 instances filtered for:
- Patches touching 3+ files
- 50+ lines changed
- Diverse repositories

These are the tasks where cross-file understanding matters most.

## Evaluation

The SWE-bench harness:
1. Checks out the repo at `base_commit`
2. Applies your predicted patch
3. Runs the `test_patch` tests
4. Reports pass/fail

Install the harness:
```bash
pip install swebench
```
