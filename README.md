# comprehend-benchmark

Empirical comparison of Claude Code with and without the
[comprehend](https://github.com/johnwbyrd/comprehend) skill on code
understanding and editing benchmarks.

## What this measures

The comprehend skill claims two things:

1. **Deeper understanding** -- by fanning out subagents and accumulating
   findings in a persistent REPL, it builds richer cross-file knowledge
   than reading files directly into the context window.

2. **Lower context cost** -- the main agent's context window stays small
   because subagents do the reading. This leaves more room for follow-up
   work.

This benchmark tests both claims by running the same tasks with and
without comprehend installed, measuring accuracy *and* token consumption.

## Benchmarks

| Benchmark | What it tests | Why it matters for comprehend |
|:----------|:-------------|:-----------------------------|
| [SWE-bench Lite](https://www.swebench.com/SWE-bench/) | Fix real GitHub issues (300 tasks) | Tests whether deeper understanding produces better patches |
| [SWE-QA](https://arxiv.org/abs/2509.14635) | Answer questions about repositories | Tests comprehension quality directly -- cross-file reasoning, dependency analysis |
| [RepoQA](https://arxiv.org/html/2406.06025v1) | Find functions from natural-language descriptions | Tests code search and understanding across 50 repos in 5 languages |

## Prerequisites

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
  with a valid API key (`ANTHROPIC_API_KEY` set in your environment)
- Docker (for SWE-bench evaluation harness)
- Git

## Quick start

```bash
# Clone and install
git clone https://github.com/johnwbyrd/comprehend-benchmark.git
cd comprehend-benchmark
uv sync

# Run a single SWE-bench task as a sanity check
bash scripts/run_one.sh baseline /tmp/test-repo \
  "What does this project do?" results/test.json

# Run the curated SWE-bench subset (20-30 tasks, ~1 hour per config)
python benchmarks/swebench_lite/run_tasks.py --config configs/baseline.json
python benchmarks/swebench_lite/run_tasks.py --config configs/comprehend.json

# Compare results
python analysis/compare.py \
  results/swebench_lite/baseline/ \
  results/swebench_lite/comprehend/
```

## Full evaluation

### SWE-bench Lite (all 300 tasks)

```bash
# Run both configs (expect ~10-20 hours each depending on model speed)
python benchmarks/swebench_lite/run_tasks.py \
  --config configs/baseline.json --all

python benchmarks/swebench_lite/run_tasks.py \
  --config configs/comprehend.json --all

# Evaluate patches using the official SWE-bench harness
python benchmarks/swebench_lite/evaluate.py \
  results/swebench_lite/baseline/predictions.jsonl

python benchmarks/swebench_lite/evaluate.py \
  results/swebench_lite/comprehend/predictions.jsonl
```

### SWE-QA

```bash
python benchmarks/swe_qa/run_tasks.py --config configs/baseline.json
python benchmarks/swe_qa/run_tasks.py --config configs/comprehend.json
```

### RepoQA

```bash
python benchmarks/repo_qa/run_tasks.py --config configs/baseline.json
python benchmarks/repo_qa/run_tasks.py --config configs/comprehend.json
```

## Methodology

### A/B setup

The two configurations differ only in whether the comprehend skill is
installed:

- **Baseline** (`configs/baseline.json`): No comprehend skill. Claude
  Code uses its built-in Explore subagents and direct file reading.

- **Comprehend** (`configs/comprehend.json`): The comprehend skill is
  installed in `.claude/skills/`. Claude Code uses the measure-first
  workflow, persistent REPL, and fan-out patterns described in the skill.

Both configs use the same model, temperature, and tool permissions.

### How a task runs

1. Check out the repository at the correct base commit
2. Install the appropriate `.claude/skills/` directory (or none)
3. Run `claude -p "<task prompt>" --output-format json --allowedTools "Bash,Read,Write,Edit,Glob,Grep"`
4. Capture the JSON output (includes token counts, session metadata)
5. For SWE-bench: capture `git diff` as the prediction patch
6. For SWE-QA/RepoQA: capture the text answer
7. Record wall time, token usage, and tool call count

### Metrics

| Metric | What it tells you |
|:-------|:-----------------|
| **Pass rate** | Did the patch/answer pass the benchmark's evaluation? |
| **Total tokens** | How many tokens were consumed (input + output)? |
| **Wall time** | How long did the task take? |
| **Tool calls** | How many tool invocations were made? |

### Statistical considerations

LLM outputs are non-deterministic. For rigorous results:

- Run each task **3 times** per configuration (pass@3)
- Use **McNemar's test** for pass/fail comparisons
- Use **paired t-test** or **Wilcoxon signed-rank** for continuous
  metrics (tokens, time)
- Report **confidence intervals**, not just point estimates

### Curated subset

The full SWE-bench Lite is 300 tasks. For quick iteration, we provide a
curated subset of 20-30 tasks (`benchmarks/swebench_lite/sample_tasks.json`)
filtered for:

- Patches touching **3+ files** (cross-file understanding matters)
- Non-trivial patches (**50+ lines** changed)
- Tasks from **diverse repositories** (not all from one project)

This subset is where comprehend's value should be most visible. Run the
full set for publishable results.

## Interpreting results

Comprehend's value is **not** just "higher pass rate." The interesting
comparisons are:

- **Same accuracy, fewer tokens**: comprehend achieves comparable results
  while consuming less context, leaving more room for follow-up work.

- **Higher accuracy on complex tasks**: comprehend may not help on simple
  one-file bugs but should shine on multi-file changes requiring
  architectural understanding.

- **Token cost breakdown**: comprehend spends tokens upfront (subagents,
  REPL) but may save tokens later by avoiding re-reading files. Compare
  total cost across the full session, not just the first pass.

## Known limitations

- **Non-determinism**: LLM outputs vary between runs. Multiple runs per
  task are essential for statistical validity.

- **Cost**: Each SWE-bench task is a full agent run. 300 tasks x 2
  configs x 3 runs = 1,800 runs. Budget accordingly.

- **Task selection bias**: SWE-bench tasks are "fix this bug given the
  issue description." Comprehend is designed for "understand this
  codebase first, then act." The benchmark may understate comprehend's
  value for exploratory tasks.

- **Model dependency**: Results are specific to the Claude model used.
  Different models may benefit differently from structured comprehension.

## Project structure

```
comprehend-benchmark/
├── README.md                   # This file
├── pyproject.toml              # Project config
├── configs/
│   ├── baseline.json           # Claude Code settings without comprehend
│   └── comprehend.json         # Claude Code settings with comprehend
├── benchmarks/
│   ├── swebench_lite/
│   │   ├── README.md           # SWE-bench specific instructions
│   │   ├── run_tasks.py        # Run SWE-bench tasks
│   │   ├── evaluate.py         # Evaluate predictions
│   │   └── sample_tasks.json   # Curated multi-file subset
│   ├── swe_qa/
│   │   ├── README.md           # SWE-QA specific instructions
│   │   └── run_tasks.py        # Run SWE-QA tasks
│   └── repo_qa/
│       ├── README.md           # RepoQA specific instructions
│       └── run_tasks.py        # Run RepoQA tasks
├── analysis/
│   ├── compare.py              # Compare results between configs
│   └── report.py               # Generate summary report
└── scripts/
    └── run_one.sh              # Run a single task
```

## License

MIT
