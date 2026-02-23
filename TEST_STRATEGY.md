# Test Strategy: Comprehend vs Baseline on SWE-bench Lite

## Goal

Determine whether the comprehend skill improves an LLM's ability to solve
hard software engineering tasks, measured as **smartness per token**: correct
patches produced relative to tokens consumed.

The benchmark is model-agnostic. Any model supported by Claude Code's
`--model` flag can be tested. The first run uses Sonnet (available on Max
at no per-token cost), but the framework supports repeating with any model.

## Benchmark

SWE-bench Lite: 300 real GitHub issues with ground-truth test suites.
Evaluation is deterministic — "did the tests pass" — no LLM judge.

## Configuration

Both configs use identical settings except for the comprehend skill.
The model is set in the config JSON and can be changed per run:

| Setting | Baseline | Comprehend |
|---------|----------|------------|
| Model | (configurable) | (configurable) |
| Max turns | 200 | 200 |
| Allowed tools | Bash,Read,Write,Edit,Glob,Grep | Bash,Read,Write,Edit,Glob,Grep |
| Comprehend skill | No | Yes |

To test a different model, change the `model` field in both config files.
Keep both configs on the same model for a valid A/B comparison.

## Metrics to capture per task

- **resolved**: did the ground-truth tests pass (binary)
- **total_tokens**: input + output + cache tokens consumed
- **wall_time_seconds**: elapsed time
- **num_turns**: agentic turns used
- **git_diff**: the patch produced (for manual inspection)

## Phase 1: Baseline run (all 300 tasks)

Run baseline config on all 300 SWE-bench Lite tasks.

```bash
python benchmarks/swebench_lite/run_tasks.py --config configs/baseline.json --all
```

Expected: ~4-5 hours wall time per model.

Outputs:
- Per-task result JSON in `results/swebench_lite/baseline/`
- Identify the **failure set**: tasks where baseline did not produce a passing patch

Expected failure set size varies by model. For Sonnet: ~100-120 tasks based
on published resolve rates. Weaker models will have larger failure sets;
stronger models smaller.

## Phase 2: Comprehend run (failure set only)

Run comprehend config on only the tasks that baseline failed.

```bash
python benchmarks/swebench_lite/run_tasks.py \
    --config configs/comprehend.json \
    --instance-id <id1> --instance-id <id2> ...
```

Or add a `--failures-from` flag that reads baseline results and runs only unresolved tasks.

Expected: ~2-3 hours depending on failure set size.

## Phase 3: Analyze

For each task in the failure set, compare:

| Metric | What it tells us |
|--------|-----------------|
| **Comprehend resolves, baseline didn't** | Comprehend helped |
| **Both fail** | Task is beyond current capability |
| **Tokens used (comprehend vs baseline)** | Cost of the comprehend overhead |
| **Turns used** | Whether comprehend's analysis phase pays off |

Key questions:
1. What fraction of baseline failures does comprehend fix?
2. What is the token overhead of comprehend on tasks it solves?
3. Are there patterns in what comprehend fixes (multi-file, specific repos)?
4. Does the benefit vary by model? (comprehend may help weaker models more)

## Phase 4: Regression check (conditional)

Only if Phase 2 shows improvement: run comprehend on the full 300 to verify
it doesn't regress on tasks baseline already solves.

If comprehend shows no improvement on the failure set, skip this phase.

## Phase 5: Cross-model comparison (optional)

Repeat Phases 1-3 with a different model to test whether comprehend's
benefit is model-dependent. Candidate models:

- claude-sonnet-4-6 (first run, free on Max)
- claude-opus-4-6 (stronger baseline, smaller failure set)
- claude-haiku-4-5 (weaker baseline, larger failure set — may benefit most)

If comprehend helps Haiku more than Sonnet, that's strong evidence it
compensates for model capability rather than just adding overhead.

## Repository difficulty reference

From published Sonnet results on SWE-bench Lite:

| Repository | Tasks | Est. Fail Rate | Est. Failures |
|-----------|------:|---------------:|--------------:|
| django/django | 114 | ~28% | ~32 |
| sympy/sympy | 77 | ~32% | ~25 |
| matplotlib/matplotlib | 23 | ~50% | ~12 |
| sphinx-doc/sphinx | 16 | ~48% | ~8 |
| pytest-dev/pytest | 17 | ~32% | ~5 |
| pylint-dev/pylint | 6 | ~90% | ~5 |
| mwaskom/seaborn | 4 | ~100% | ~4 |
| psf/requests | 6 | ~63% | ~4 |
| scikit-learn/scikit-learn | 23 | ~16% | ~4 |
| astropy/astropy | 6 | ~45% | ~3 |
| pydata/xarray | 5 | ~18% | ~1 |
| pallets/flask | 3 | ~0% | ~0 |

Multi-file changes are the dominant failure predictor across all repos.
These numbers will differ for other models.

## Decision criteria

- **Proceed to Phase 4** if comprehend resolves >10% of baseline failures
- **Ship as evidence** if comprehend resolves >20% of baseline failures
  without meaningful regression on the passing set
- **Abandon SWE-bench approach** if comprehend resolves <5% of baseline failures;
  consider SWE-QA or RepoQA instead (comprehension-focused, not patch-focused)
