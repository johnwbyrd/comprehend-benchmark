"""Evaluate SWE-bench predictions using the official harness.

Usage:
    python evaluate.py results/baseline/predictions.jsonl
    python evaluate.py results/comprehend/predictions.jsonl --dataset SWE-bench_Lite

Requires:
    pip install swebench
    Docker must be installed and running.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Evaluate SWE-bench predictions")
    parser.add_argument("predictions", help="Path to predictions JSONL file")
    parser.add_argument("--dataset", default="princeton-nlp/SWE-bench_Lite",
                        help="HuggingFace dataset name")
    parser.add_argument("--max-workers", type=int, default=4,
                        help="Number of parallel evaluation workers")
    parser.add_argument("--run-id", default=None,
                        help="Identifier for this evaluation run")
    args = parser.parse_args()

    predictions_path = Path(args.predictions).resolve()
    if not predictions_path.exists():
        print(f"Error: {predictions_path} not found", file=sys.stderr)
        sys.exit(1)

    run_id = args.run_id or predictions_path.stem

    print(f"Evaluating: {predictions_path}")
    print(f"Dataset:    {args.dataset}")
    print(f"Workers:    {args.max_workers}")
    print(f"Run ID:     {run_id}")

    # TODO: Verify Docker is running
    # subprocess.run(["docker", "info"], check=True, capture_output=True)

    cmd = [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "--dataset_name", args.dataset,
        "--predictions_path", str(predictions_path),
        "--max_workers", str(args.max_workers),
        "--run_id", run_id,
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")

    # TODO: Uncomment to actually run evaluation
    # subprocess.run(cmd, check=True)

    print("TODO: Uncomment subprocess.run() call above to run evaluation")
    print("      Requires: pip install swebench && Docker running")


if __name__ == "__main__":
    main()
