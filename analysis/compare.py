"""Compare results between baseline and comprehend configurations.

Usage:
    python compare.py runs/swebench_lite/baseline/results/ runs/swebench_lite/comprehend/results/
    python compare.py runs/swe_qa/baseline/results/ runs/swe_qa/comprehend/results/

Loads result JSONs from both directories, computes comparative metrics,
and prints a summary table.
"""

import argparse
import json
import sys
from pathlib import Path


def load_results(results_dir: Path) -> dict[str, dict]:
    """Load all result JSONs from a directory, keyed by task ID."""
    results = {}
    for f in sorted(results_dir.glob("*.json")):
        if f.name in ("summary.json", "predictions.jsonl"):
            continue
        with open(f) as fh:
            data = json.load(fh)
        task_id = data.get("instance_id") or data.get("task_id") or f.stem
        results[task_id] = data
    return results


def compare_swebench(baseline: dict, comprehend: dict):
    """Compare SWE-bench results (patch-based, pass/fail from evaluation)."""
    common = set(baseline.keys()) & set(comprehend.keys())
    if not common:
        print("No common tasks found between the two result sets.")
        return

    print(f"\nSWE-bench Lite Comparison ({len(common)} common tasks)")
    print("=" * 60)

    # TODO: Pass/fail requires running the SWE-bench evaluation harness first.
    # For now, compare available metrics: wall time, tokens, git diff size.

    metrics = {
        "wall_time": ("wall_time_seconds", "Wall time (seconds)"),
        "diff_size": ("git_diff", "Patch size (chars)"),
    }

    for key, (field, label) in metrics.items():
        b_vals = [baseline[t].get(field, 0) for t in common]
        c_vals = [comprehend[t].get(field, 0) for t in common]

        if key == "diff_size":
            b_vals = [len(str(v)) for v in b_vals]
            c_vals = [len(str(v)) for v in c_vals]

        b_mean = sum(b_vals) / max(len(b_vals), 1)
        c_mean = sum(c_vals) / max(len(c_vals), 1)
        diff_pct = ((c_mean - b_mean) / max(b_mean, 0.001)) * 100

        print(f"\n{label}:")
        print(f"  Baseline:    {b_mean:.1f}")
        print(f"  Comprehend:  {c_mean:.1f}")
        print(f"  Difference:  {diff_pct:+.1f}%")


def compare_qa(baseline: dict, comprehend: dict, benchmark_name: str):
    """Compare Q&A-style benchmark results."""
    common = set(baseline.keys()) & set(comprehend.keys())
    if not common:
        print("No common tasks found between the two result sets.")
        return

    print(f"\n{benchmark_name} Comparison ({len(common)} common tasks)")
    print("=" * 60)

    # Compare evaluation scores
    for metric_key in ("word_overlap", "exact_match", "func_match", "correctness"):
        b_scores = []
        c_scores = []
        for t in common:
            b_eval = baseline[t].get("evaluation", {})
            c_eval = comprehend[t].get("evaluation", {})
            b_val = b_eval.get(metric_key)
            c_val = c_eval.get(metric_key)
            if b_val is not None and c_val is not None:
                b_scores.append(float(b_val))
                c_scores.append(float(c_val))

        if not b_scores:
            continue

        b_mean = sum(b_scores) / len(b_scores)
        c_mean = sum(c_scores) / len(c_scores)

        print(f"\n{metric_key}:")
        print(f"  Baseline:    {b_mean:.3f}")
        print(f"  Comprehend:  {c_mean:.3f}")
        print(f"  Difference:  {c_mean - b_mean:+.3f}")


def main():
    parser = argparse.ArgumentParser(description="Compare benchmark results")
    parser.add_argument("baseline_dir", help="Path to baseline results directory")
    parser.add_argument("comprehend_dir", help="Path to comprehend results directory")
    parser.add_argument("--benchmark", choices=["swebench", "swe_qa", "repo_qa"],
                        default=None, help="Benchmark type (auto-detected from path)")
    args = parser.parse_args()

    baseline_dir = Path(args.baseline_dir)
    comprehend_dir = Path(args.comprehend_dir)

    if not baseline_dir.exists():
        print(f"Error: {baseline_dir} not found", file=sys.stderr)
        sys.exit(1)
    if not comprehend_dir.exists():
        print(f"Error: {comprehend_dir} not found", file=sys.stderr)
        sys.exit(1)

    baseline = load_results(baseline_dir)
    comprehend = load_results(comprehend_dir)

    print(f"Baseline results:    {len(baseline)} tasks")
    print(f"Comprehend results:  {len(comprehend)} tasks")

    # Auto-detect benchmark type from path
    benchmark = args.benchmark
    if not benchmark:
        path_str = str(baseline_dir)
        if "swebench" in path_str:
            benchmark = "swebench"
        elif "swe_qa" in path_str:
            benchmark = "swe_qa"
        elif "repo_qa" in path_str:
            benchmark = "repo_qa"

    if benchmark == "swebench":
        compare_swebench(baseline, comprehend)
    elif benchmark in ("swe_qa", "repo_qa"):
        compare_qa(baseline, comprehend, benchmark.upper().replace("_", "-"))
    else:
        print("\nCould not detect benchmark type. Showing raw comparison.")
        compare_swebench(baseline, comprehend)

    # TODO: Add statistical significance tests
    # - McNemar's test for pass/fail
    # - Wilcoxon signed-rank for continuous metrics
    print("\n\nTODO: Add statistical significance tests (McNemar's, Wilcoxon)")


if __name__ == "__main__":
    main()
