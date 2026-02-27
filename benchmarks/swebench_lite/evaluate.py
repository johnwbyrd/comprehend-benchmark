"""Evaluate SWE-bench predictions using the official harness.

Usage:
    uv run bench-swebench-eval runs/swebench_lite/baseline/predictions.jsonl
    uv run bench-swebench-eval runs/swebench_lite/comprehend/predictions.jsonl

Requires:
    uv sync --extra swebench
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

    # Check Docker is running
    try:
        subprocess.run(
            ["docker", "info"], check=True, capture_output=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: Docker is not running or not installed.", file=sys.stderr)
        print("SWE-bench evaluation requires Docker.", file=sys.stderr)
        sys.exit(1)

    # Check swebench is installed
    try:
        import swebench  # noqa: F401
    except ImportError:
        print("Error: swebench not installed.", file=sys.stderr)
        print("Run: uv sync --extra swebench", file=sys.stderr)
        sys.exit(1)

    run_id = args.run_id or predictions_path.stem

    print(f"Evaluating: {predictions_path}")
    print(f"Dataset:    {args.dataset}")
    print(f"Workers:    {args.max_workers}")
    print(f"Run ID:     {run_id}")

    cmd = [
        sys.executable, "-m", "swebench.harness.run_evaluation",
        "--dataset_name", args.dataset,
        "--predictions_path", str(predictions_path),
        "--max_workers", str(args.max_workers),
        "--run_id", run_id,
    ]

    print(f"\nRunning: {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
