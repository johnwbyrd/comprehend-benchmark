# Findings: Comprehend vs Baseline on SWE-bench Lite

## Summary

The comprehend skill was tested against vanilla Claude Code (baseline) on
all 61 SWE-bench Lite tasks across 6 high-fail-rate repositories, with
both configurations running on every task for a fair A/B comparison.

**Comprehend resolved 37/61 tasks (61%) vs baseline's 32/61 (52%).**
Net gain: +5 tasks. Comprehend fixed 9 tasks baseline couldn't, but
regressed on 4 tasks baseline solved. 28 tasks were solved by both,
20 by neither.

Both configurations used `claude-sonnet-4-6` with identical settings
(200 max turns, same allowed tools). The only difference: comprehend
installs the comprehend skill and uses a slightly different system prompt
that encourages thorough codebase analysis before making changes.

## Experimental Design

### Benchmark: SWE-bench Lite

300 real GitHub issues with ground-truth test suites
(`princeton-nlp/SWE-bench_Lite`, test split). Evaluation is deterministic:
the agent produces a patch, and the SWE-bench harness runs the issue's
test suite in Docker to check if the patch resolves the issue.

### Benchmarks Considered and Rejected

- **SWE-QA** (swe-qa/SWE-QA-Benchmark): 576 question-answer pairs about
  codebases, scored by LLM-as-judge on 5 dimensions (correctness,
  completeness, relevance, clarity, reasoning quality). Rejected due to
  **ceiling effect**: Claude 3.7 Sonnet + SWE-QA-Agent already scores
  47.82/50 (9.36/10 on correctness alone). No room to demonstrate
  improvement.
- **RepoQA**: Tests code search, not comprehension. Wrong fit for
  measuring comprehend's value (measure-first analysis workflow).

### Repo Selection Strategy

Rather than running all 300 tasks, we targeted repositories with the
highest estimated failure rates (from published Sonnet results on
SWE-bench Lite). This maximizes signal for comprehend's value on hard
tasks:

| Repository | Tasks | Est. Fail Rate | Actual Fail Rate |
|-----------|------:|---------------:|----------------:|
| pylint-dev/pylint | 6 | ~90% | 67% |
| mwaskom/seaborn | 4 | ~100% | 25% |
| psf/requests | 6 | ~63% | 50% |
| matplotlib/matplotlib | 23 | ~50% | 48% |
| sphinx-doc/sphinx | 16 | ~48% | 50% |
| astropy/astropy | 6 | ~45% | 33% |
| **Total** | **61** | | **48%** |

### Phase Strategy

1. **Baseline run**: Run vanilla Claude Code on all 61 tasks
2. **Identify failures**: 32 resolved, 29 unresolved
3. **Comprehend run (failures)**: Run comprehend on the 29 failures + 2
   regression checks = 31 tasks
4. **Comprehend run (full)**: Run comprehend on remaining 30 baseline
   successes for fair A/B comparison = 61 total
5. **Evaluate**: SWE-bench Docker harness on both full prediction sets

## Results

### Headline Numbers

| Metric | Baseline | Comprehend |
|--------|----------|------------|
| Resolved | 32/61 (52%) | **37/61 (61%)** |
| Total wall time | 16,955s (4.7h) | 21,038s (5.8h) |
| Total cost | $75.51 | $106.83 |
| Avg time/task | 278s | 345s |
| Avg cost/task | $1.24 | $1.75 |

| Comparison | Count |
|------------|------:|
| Both pass | 28 |
| Only baseline (regressions) | 4 |
| Only comprehend (new fixes) | 9 |
| Both fail | 20 |
| **Net gain** | **+5** |

Decision threshold met: >20% fix rate on failures ("ship as evidence").

### What Comprehend Fixed (9 tasks)

| Task | Baseline | Comprehend |
|------|----------|------------|
| astropy\_\_astropy-14365 | FAIL, 105s, $0.48, 17 turns | **PASS**, 138s, $0.75, 2 turns |
| matplotlib\_\_matplotlib-23562 | FAIL, 23s, $0.15, 4 turns | **PASS**, 18s, $0.12, 4 turns |
| matplotlib\_\_matplotlib-25079 | FAIL, 1109s, $4.22, 62 turns | **PASS**, 912s, $4.72, 84 turns |
| matplotlib\_\_matplotlib-25311 | FAIL, 857s, $4.40, 81 turns | **PASS**, 663s, $3.60, 66 turns |
| matplotlib\_\_matplotlib-25442 | FAIL, 977s, $4.81, 70 turns | **PASS**, 466s, $2.04, 36 turns |
| mwaskom\_\_seaborn-3407 | FAIL, 589s, $2.27, 43 turns | **PASS**, 231s, $0.85, 25 turns |
| psf\_\_requests-2674 | FAIL, 102s, $0.39, 14 turns | **PASS**, 135s, $0.59, 17 turns |
| psf\_\_requests-863 | FAIL, 31s, $0.18, 7 turns | **PASS**, 32s, $0.18, 8 turns |
| pylint-dev\_\_pylint-7228 | FAIL, 292s, $1.76, 46 turns | **PASS**, 370s, $1.79, 48 turns |

### What Comprehend Regressed (4 tasks)

| Task | Baseline | Comprehend |
|------|----------|------------|
| matplotlib\_\_matplotlib-24970 | **PASS**, 211s, $0.70, 19 turns | FAIL, 120s, $0.53, 14 turns |
| matplotlib\_\_matplotlib-25498 | **PASS**, 256s, $0.78, 16 turns | FAIL, 291s, $1.54, 44 turns |
| mwaskom\_\_seaborn-3190 | **PASS**, 157s, $0.84, 34 turns | FAIL, 83s, $0.44, 19 turns |
| psf\_\_requests-2317 | **PASS**, 32s, $0.17, 8 turns | FAIL, 36s, $0.25, 12 turns |

Two of the regressions (matplotlib-24970, seaborn-3190) are cases where
comprehend spent *less* time and *fewer* turns — suggesting it may have
taken a shortcut that produced an incorrect patch rather than being
stumped by the problem.

### Per-Repo Breakdown (Baseline)

| Repo | Resolved | Total | Resolve Rate | Avg Time | Total Cost |
|------|----------|-------|-------------|----------|------------|
| astropy/astropy | 4 | 6 | 67% | 177s | $5.53 |
| matplotlib/matplotlib | 12 | 23 | 52% | 267s | $26.71 |
| mwaskom/seaborn | 3 | 4 | 75% | 245s | $3.90 |
| psf/requests | 3 | 6 | 50% | 89s | $2.44 |
| pylint-dev/pylint | 2 | 6 | 33% | 286s | $7.95 |
| sphinx-doc/sphinx | 8 | 16 | 50% | 408s | $28.99 |
| **Total** | **32** | **61** | **52%** | **278s** | **$75.51** |

### Per-Repo Comparison (full run)

| Repo | Baseline | Comprehend | New Fixes | Regressions | Net |
|------|----------|------------|----------:|------------:|----:|
| astropy/astropy | 4/6 (67%) | 5/6 (83%) | 1 | 0 | +1 |
| matplotlib/matplotlib | 12/23 (52%) | 14/23 (61%) | 4 | 2 | +2 |
| mwaskom/seaborn | 3/4 (75%) | 3/4 (75%) | 1 | 1 | 0 |
| psf/requests | 3/6 (50%) | 4/6 (67%) | 2 | 1 | +1 |
| pylint-dev/pylint | 2/6 (33%) | 3/6 (50%) | 1 | 0 | +1 |
| sphinx-doc/sphinx | 8/16 (50%) | 8/16 (50%) | 0 | 0 | 0 |
| **Total** | **32/61 (52%)** | **37/61 (61%)** | **9** | **4** | **+5** |

Sphinx is the only repo where comprehend showed zero change. Seaborn
was a wash (1 fix, 1 regression).

### Cost Analysis

Comprehend costs more overall: $106.83 vs $75.51 (41% more) for the same
61 tasks. Average cost per task: $1.75 comprehend vs $1.24 baseline.
Average wall time: 345s vs 278s (24% slower).

The cost increase is driven by expensive failures where comprehend
persists longer without making progress:

- `pylint-dev__pylint-7080`: $9.66 / 2667s (comprehend) vs $1.64 / 349s (baseline) — both failed
- `matplotlib__matplotlib-23299`: $8.45 / 1156s (comprehend) vs $2.00 / 534s (baseline) — both failed
- `sphinx-doc__sphinx-10325`: $8.06 / 1194s (comprehend) vs $1.99 / 359s (baseline) — both passed
- `sphinx-doc__sphinx-8474`: $7.77 / 1655s (comprehend) vs $5.61 / 1235s (baseline) — both failed

The extra 5 resolved tasks come at a cost of ~$31 more total ($106.83 -
$75.51), or ~$6.26 per additional fix.

## Complete Per-Task Results

### Baseline (61 tasks)

| Instance ID | Result | Time | Cost | Turns |
|-------------|--------|-----:|-----:|------:|
| astropy\_\_astropy-12907 | PASS | 88s | $0.47 | 14 |
| astropy\_\_astropy-14182 | PASS | 467s | $2.46 | 66 |
| astropy\_\_astropy-14365 | FAIL | 105s | $0.48 | 17 |
| astropy\_\_astropy-14995 | PASS | 137s | $0.73 | 27 |
| astropy\_\_astropy-6938 | PASS | 128s | $0.72 | 2 |
| astropy\_\_astropy-7746 | FAIL | 139s | $0.66 | 18 |
| matplotlib\_\_matplotlib-18869 | FAIL | 50s | $0.33 | 14 |
| matplotlib\_\_matplotlib-22711 | FAIL | 54s | $0.26 | 7 |
| matplotlib\_\_matplotlib-22835 | FAIL | 128s | $0.93 | 2 |
| matplotlib\_\_matplotlib-23299 | FAIL | 534s | $2.00 | 40 |
| matplotlib\_\_matplotlib-23314 | PASS | 58s | $0.18 | 4 |
| matplotlib\_\_matplotlib-23476 | FAIL | 159s | $0.79 | 20 |
| matplotlib\_\_matplotlib-23562 | FAIL | 23s | $0.15 | 4 |
| matplotlib\_\_matplotlib-23563 | FAIL | 269s | $0.97 | 22 |
| matplotlib\_\_matplotlib-23913 | PASS | 89s | $0.48 | 21 |
| matplotlib\_\_matplotlib-23964 | PASS | 20s | $0.10 | 3 |
| matplotlib\_\_matplotlib-23987 | FAIL | 206s | $0.73 | 15 |
| matplotlib\_\_matplotlib-24149 | PASS | 76s | $0.44 | 17 |
| matplotlib\_\_matplotlib-24265 | PASS | 96s | $0.49 | 17 |
| matplotlib\_\_matplotlib-24334 | PASS | 74s | $0.42 | 17 |
| matplotlib\_\_matplotlib-24970 | PASS | 211s | $0.70 | 19 |
| matplotlib\_\_matplotlib-25079 | FAIL | 1109s | $4.22 | 62 |
| matplotlib\_\_matplotlib-25311 | FAIL | 857s | $4.40 | 81 |
| matplotlib\_\_matplotlib-25332 | PASS | 412s | $1.45 | 39 |
| matplotlib\_\_matplotlib-25433 | PASS | 217s | $0.64 | 13 |
| matplotlib\_\_matplotlib-25442 | FAIL | 977s | $4.81 | 70 |
| matplotlib\_\_matplotlib-25498 | PASS | 256s | $0.78 | 16 |
| matplotlib\_\_matplotlib-26011 | PASS | 44s | $0.26 | 9 |
| matplotlib\_\_matplotlib-26020 | PASS | 223s | $1.20 | 26 |
| mwaskom\_\_seaborn-2848 | PASS | 221s | $0.74 | 16 |
| mwaskom\_\_seaborn-3010 | PASS | 12s | $0.05 | 3 |
| mwaskom\_\_seaborn-3190 | PASS | 157s | $0.84 | 34 |
| mwaskom\_\_seaborn-3407 | FAIL | 589s | $2.27 | 43 |
| psf\_\_requests-1963 | FAIL | 27s | $0.13 | 5 |
| psf\_\_requests-2148 | PASS | 38s | $0.24 | 11 |
| psf\_\_requests-2317 | PASS | 32s | $0.17 | 8 |
| psf\_\_requests-2674 | FAIL | 102s | $0.39 | 14 |
| psf\_\_requests-3362 | PASS | 304s | $1.33 | 32 |
| psf\_\_requests-863 | FAIL | 31s | $0.18 | 7 |
| pylint-dev\_\_pylint-5859 | PASS | 327s | $1.36 | 32 |
| pylint-dev\_\_pylint-6506 | FAIL | 23s | $0.14 | 5 |
| pylint-dev\_\_pylint-7080 | FAIL | 349s | $1.64 | 16 |
| pylint-dev\_\_pylint-7114 | FAIL | 471s | $1.83 | 37 |
| pylint-dev\_\_pylint-7228 | FAIL | 292s | $1.76 | 46 |
| pylint-dev\_\_pylint-7993 | PASS | 252s | $1.21 | 39 |
| sphinx-doc\_\_sphinx-10325 | PASS | 359s | $1.99 | 2 |
| sphinx-doc\_\_sphinx-10451 | FAIL | 574s | $2.52 | 50 |
| sphinx-doc\_\_sphinx-11445 | PASS | 263s | $0.97 | 23 |
| sphinx-doc\_\_sphinx-7686 | FAIL | 223s | $1.00 | 29 |
| sphinx-doc\_\_sphinx-7738 | FAIL | 248s | $0.92 | 25 |
| sphinx-doc\_\_sphinx-7975 | PASS | 282s | $1.01 | 21 |
| sphinx-doc\_\_sphinx-8273 | FAIL | 138s | $0.64 | 19 |
| sphinx-doc\_\_sphinx-8282 | FAIL | 349s | $1.55 | 1 |
| sphinx-doc\_\_sphinx-8435 | PASS | 1389s | $6.65 | 1 |
| sphinx-doc\_\_sphinx-8474 | FAIL | 1235s | $5.61 | 83 |
| sphinx-doc\_\_sphinx-8506 | FAIL | 515s | $2.01 | 39 |
| sphinx-doc\_\_sphinx-8595 | FAIL | 28s | $0.17 | 7 |
| sphinx-doc\_\_sphinx-8627 | PASS | 424s | $1.78 | 37 |
| sphinx-doc\_\_sphinx-8713 | PASS | 17s | $0.12 | 5 |
| sphinx-doc\_\_sphinx-8721 | PASS | 20s | $0.13 | 4 |
| sphinx-doc\_\_sphinx-8801 | PASS | 458s | $1.92 | 52 |

**Totals:** 16,955s wall time, $75.51 cost, 32 resolved

### Comprehend (61 tasks — full run)

| Instance ID | Result | Time | Cost | Turns |
|-------------|--------|-----:|-----:|------:|
| astropy\_\_astropy-12907 | **PASS** | 136s | $0.77 | 25 |
| astropy\_\_astropy-14182 | **PASS** | 526s | $3.25 | 66 |
| astropy\_\_astropy-14365 | **PASS** | 138s | $0.75 | 2 |
| astropy\_\_astropy-14995 | **PASS** | 225s | $1.19 | 1 |
| astropy\_\_astropy-6938 | **PASS** | 19s | $0.12 | 4 |
| astropy\_\_astropy-7746 | FAIL | 99s | $0.50 | 15 |
| matplotlib\_\_matplotlib-18869 | FAIL | 102s | $0.57 | 25 |
| matplotlib\_\_matplotlib-22711 | FAIL | 91s | $0.38 | 10 |
| matplotlib\_\_matplotlib-22835 | FAIL | 126s | $0.81 | 1 |
| matplotlib\_\_matplotlib-23299 | FAIL | 1156s | $8.45 | 2 |
| matplotlib\_\_matplotlib-23314 | **PASS** | 49s | $0.18 | 5 |
| matplotlib\_\_matplotlib-23476 | FAIL | 194s | $0.82 | 21 |
| matplotlib\_\_matplotlib-23562 | **PASS** | 18s | $0.12 | 4 |
| matplotlib\_\_matplotlib-23563 | FAIL | 703s | $3.37 | 2 |
| matplotlib\_\_matplotlib-23913 | **PASS** | 59s | $0.39 | 20 |
| matplotlib\_\_matplotlib-23964 | **PASS** | 61s | $0.40 | 16 |
| matplotlib\_\_matplotlib-23987 | FAIL | 138s | $0.50 | 8 |
| matplotlib\_\_matplotlib-24149 | **PASS** | 106s | $0.46 | 15 |
| matplotlib\_\_matplotlib-24265 | **PASS** | 146s | $0.69 | 20 |
| matplotlib\_\_matplotlib-24334 | **PASS** | 222s | $1.03 | 39 |
| matplotlib\_\_matplotlib-24970 | FAIL | 120s | $0.53 | 14 |
| matplotlib\_\_matplotlib-25079 | **PASS** | 912s | $4.72 | 84 |
| matplotlib\_\_matplotlib-25311 | **PASS** | 663s | $3.60 | 66 |
| matplotlib\_\_matplotlib-25332 | **PASS** | 164s | $0.90 | 24 |
| matplotlib\_\_matplotlib-25433 | **PASS** | 578s | $3.50 | 75 |
| matplotlib\_\_matplotlib-25442 | **PASS** | 466s | $2.04 | 36 |
| matplotlib\_\_matplotlib-25498 | FAIL | 291s | $1.54 | 44 |
| matplotlib\_\_matplotlib-26011 | **PASS** | 25s | $0.18 | 7 |
| matplotlib\_\_matplotlib-26020 | **PASS** | 241s | $1.55 | 40 |
| mwaskom\_\_seaborn-2848 | **PASS** | 865s | $6.42 | 106 |
| mwaskom\_\_seaborn-3010 | **PASS** | 11s | $0.09 | 3 |
| mwaskom\_\_seaborn-3190 | FAIL | 83s | $0.44 | 19 |
| mwaskom\_\_seaborn-3407 | **PASS** | 231s | $0.85 | 25 |
| psf\_\_requests-1963 | FAIL | 25s | $0.16 | 6 |
| psf\_\_requests-2148 | **PASS** | 52s | $0.31 | 13 |
| psf\_\_requests-2317 | FAIL | 36s | $0.25 | 12 |
| psf\_\_requests-2674 | **PASS** | 135s | $0.59 | 17 |
| psf\_\_requests-3362 | **PASS** | 37s | $0.27 | 10 |
| psf\_\_requests-863 | **PASS** | 32s | $0.18 | 8 |
| pylint-dev\_\_pylint-5859 | **PASS** | 372s | $1.23 | 30 |
| pylint-dev\_\_pylint-6506 | FAIL | 28s | $0.17 | 7 |
| pylint-dev\_\_pylint-7080 | FAIL | 2667s | $9.66 | 120 |
| pylint-dev\_\_pylint-7114 | FAIL | 907s | $4.52 | 80 |
| pylint-dev\_\_pylint-7228 | **PASS** | 370s | $1.79 | 48 |
| pylint-dev\_\_pylint-7993 | **PASS** | 267s | $1.19 | 25 |
| sphinx-doc\_\_sphinx-10325 | **PASS** | 1194s | $8.06 | 2 |
| sphinx-doc\_\_sphinx-10451 | FAIL | 714s | $2.90 | 60 |
| sphinx-doc\_\_sphinx-11445 | **PASS** | 236s | $0.84 | 18 |
| sphinx-doc\_\_sphinx-7686 | FAIL | 405s | $1.58 | 2 |
| sphinx-doc\_\_sphinx-7738 | FAIL | 437s | $1.88 | 52 |
| sphinx-doc\_\_sphinx-7975 | **PASS** | 183s | $0.73 | 17 |
| sphinx-doc\_\_sphinx-8273 | FAIL | 185s | $0.86 | 29 |
| sphinx-doc\_\_sphinx-8282 | FAIL | 226s | $1.13 | 32 |
| sphinx-doc\_\_sphinx-8435 | **PASS** | 762s | $4.24 | 2 |
| sphinx-doc\_\_sphinx-8474 | FAIL | 1655s | $7.77 | 111 |
| sphinx-doc\_\_sphinx-8506 | FAIL | 492s | $2.27 | 47 |
| sphinx-doc\_\_sphinx-8595 | FAIL | 17s | $0.11 | 4 |
| sphinx-doc\_\_sphinx-8627 | **PASS** | 322s | $1.52 | 33 |
| sphinx-doc\_\_sphinx-8713 | **PASS** | 17s | $0.12 | 5 |
| sphinx-doc\_\_sphinx-8721 | **PASS** | 26s | $0.15 | 4 |
| sphinx-doc\_\_sphinx-8801 | **PASS** | 275s | $1.22 | 36 |

**Totals:** 21,038s wall time (5.8h), $106.83 cost, 37 resolved

## Timeline

### Phase 1: Initial Validation (seaborn)

1. Ran baseline on 4 seaborn tasks. Result: 3/4 resolved.
   - `seaborn-2848`: PASS (221s, $0.74) — first task ever run
   - `seaborn-3010`: PASS (12s, $0.05)
   - `seaborn-3190`: PASS (157s, $0.84)
   - `seaborn-3407`: FAIL (589s, $2.27)
2. Ran comprehend on `seaborn-3407` (the lone failure).
   Result: **PASS** (231s, $0.85). First comprehend win.
   2.5x faster, 2.7x cheaper, and actually solved the problem.
3. Evaluated both with SWE-bench Docker harness. Confirmed results.

### Phase 2: Pylint Baseline + Comprehend

4. Ran baseline on 6 pylint tasks. Result: 2/6 resolved (67% fail rate).
5. Ran comprehend on 4 pylint failures + 2 passes (regression check).
   Result: 1/4 failures fixed (pylint-7228), 0 regressions.
   Running tally: 2/5 failures fixed (40%).

### Phase 3: Remaining 4 Repos (Baseline)

6. Ran baseline on 51 tasks across requests, matplotlib, sphinx, astropy.
   - First attempt: ~12 tasks succeeded, then 39 produced zero-time
     broken results. Root cause unknown — evidence was deleted before
     investigation (see Infrastructure Issues below). Hypothesis: the
     `claude` CLI binary became unavailable mid-run (symlink at
     `~/.local/bin/claude` may have been disrupted), but this was never
     confirmed.
   - After adding error detection to `run_one.sh`, all 51 tasks were
     re-run successfully. Checkpointing skipped the ~12 already-completed
     tasks.
7. Final baseline: 32/61 resolved, 29 unresolved.

### Phase 4: Comprehend on All Failures

8. Ran comprehend on all 29 baseline failures (5 already done from
   seaborn + pylint). Checkpointing skipped existing results.
9. Evaluated with SWE-bench Docker harness.
10. Preliminary result: 9/29 failures fixed (31%).

### Phase 5: Full Fair Comparison

11. Ran comprehend on remaining 30 baseline successes to complete the
    A/B comparison. Checkpointing skipped existing 31 results.
12. Evaluated full 61-task comprehend predictions.
13. Final result: **37/61 resolved (61%) vs baseline 32/61 (52%).**
    9 new fixes, 4 regressions, net +5.

## Infrastructure Issues and Fixes

### 1. CLAUDECODE Environment Variable (Critical)

**Problem:** `claude -p` (headless mode) detected it was running inside
another Claude Code session and refused to execute. Every task produced
no output.

**Root cause:** The `CLAUDECODE` environment variable is set by the
parent Claude Code session. The child invocation inherits it and thinks
it's a nested session.

**Fix:** Added `unset CLAUDECODE` to `run_one.sh` before the `claude`
invocation.

### 2. Git Dirty Working Tree

**Problem:** After one task modifies files in a repository, the next
task's `git checkout <base_commit>` fails because of uncommitted changes
left by the previous task.

**Fix:** Added `git checkout .` (with `check=False`) before
`git checkout <base_commit>` in `checkout_repo()` to reset the working
tree between tasks.

### 3. Predictions JSONL Overwrite

**Problem:** `write_predictions()` opened with mode `"w"` (truncate),
so each run wiped the previous predictions file. Running tasks one at a
time or in batches caused data loss.

**Fix:** Changed `predictions.jsonl` and `summary.json` to rebuild from
all per-task JSON files in the results directory on every run. Per-task
JSONs serve as the source of truth.

### 4. Silent Failure / Evidence Destruction Incident

**Problem:** ~39 baseline tasks produced zero-time results with no
output. The `run_one.sh` script suppressed stderr (`2>/dev/null`) and
swallowed errors (`|| true`), producing bogus result JSONs.

**What happened:** The broken result files were deleted before they
could be examined. The actual cause of the mid-run failure was never
determined. Hypothesis was that the `claude` symlink disappeared, but
this was never confirmed ("Why would a Claude symlink break halfway
through the run?").

**Lesson learned:** Never delete evidence before investigating.
Broken output files may contain error messages, partial results, or
other diagnostic information.

**Fix:** Changed `run_one.sh` to:
- Redirect stderr to a temp file instead of `/dev/null`
- Check if `claude` produced output; exit with error if not
- Print stderr contents when failing

### 5. Checkpointing

**Problem:** Long-running batches couldn't be interrupted and resumed.
Re-running re-did completed tasks.

**Fix:** Added per-task checkpointing: skip tasks with existing result
JSONs. Delete a specific JSON to force re-run. The filesystem is the
checkpoint.

## Configuration Details

### Baseline (`configs/baseline.json`)

```json
{
  "name": "baseline",
  "skills_dir": null,
  "allowed_tools": "Bash,Read,Write,Edit,Glob,Grep",
  "max_turns": 200,
  "model": "claude-sonnet-4-6",
  "append_system_prompt": "You are solving a software engineering task. Read the issue description carefully, understand the codebase, and produce a patch that resolves the issue."
}
```

### Comprehend (`configs/comprehend.json`)

```json
{
  "name": "comprehend",
  "skills_dir": "skills/comprehend",
  "allowed_tools": "Bash,Read,Write,Edit,Glob,Grep",
  "max_turns": 200,
  "model": "claude-sonnet-4-6",
  "append_system_prompt": "You are solving a software engineering task. Read the issue description carefully. Before making changes, analyze the codebase thoroughly to understand the architecture and relevant code paths, then produce a patch that resolves the issue."
}
```

## Open Questions / Future Work

1. **Regressions**: 4 tasks regressed. Can comprehend's analysis phase
   be tuned to avoid producing worse patches on tasks baseline solves?
   Two regressions (matplotlib-24970, seaborn-3190) spent less time,
   suggesting a hasty incorrect fix rather than inability.

2. **Sphinx failures**: Comprehend fixed 0/8 sphinx failures (same as
   baseline). Is there something about sphinx issues that doesn't
   benefit from the measure-first approach?

3. **Cost of failure**: When comprehend doesn't help, it's often more
   expensive (e.g., pylint-7080: $9.66 vs $1.64). Can the skill detect
   when it's not making progress and bail out earlier?

4. **Cross-model comparison**: Would comprehend help more with a weaker
   model (Haiku) or less with a stronger model (Opus)? The test strategy
   suggests comprehend may compensate for model capability.

5. **Remaining 239 tasks**: Only 61 of 300 SWE-bench Lite tasks were
   tested. The full suite would give a more robust estimate.

6. **Root cause of broken run**: The mid-run failure where ~39 tasks
   produced zero-time results was never diagnosed (evidence destroyed).
   If it recurs, stderr capture should reveal the cause.

7. **Nondeterminism**: Both configurations are nondeterministic (LLM
   sampling). A single run per task doesn't account for variance.
   Multiple runs per task would give confidence intervals.

## Evaluation Reports

SWE-bench harness evaluation report files:

- `claude-code-baseline.baseline-all.json` — 61 submitted, 32 resolved, 29 unresolved
- `claude-code-comprehend.comprehend-full.json` — 61 submitted, 37 resolved, 24 unresolved
- `claude-code-comprehend.comprehend-all.json` — 31 submitted (early partial run)
- `claude-code-baseline.baseline-seaborn.json` — early seaborn-only eval
- `claude-code-comprehend.comprehend-seaborn.json` — early seaborn-only eval
- `claude-code-baseline.baseline-pylint.json` — early pylint-only eval
- `claude-code-comprehend.comprehend-pylint.json` — early pylint-only eval

Per-task results stored in:
- `results/swebench_lite/baseline/*.json` (61 files)
- `results/swebench_lite/comprehend/*.json` (61 files)
