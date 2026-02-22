"""Run RepoQA tasks with Claude Code headless.

Usage:
    python run_tasks.py --config ../../configs/baseline.json
    python run_tasks.py --config ../../configs/comprehend.json

RepoQA tests code search: given a natural-language description, find the
matching function in a repository.

This script:
1. Loads the RepoQA dataset
2. For each task, checks out the repo
3. Runs Claude Code headless with the function description as prompt
4. Checks if the returned function matches the ground truth
"""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RUN_ONE = PROJECT_ROOT / "scripts" / "run_one.sh"


def load_tasks():
    """Load RepoQA tasks.

    TODO: Replace with actual dataset loading.
    The RepoQA paper (arxiv.org/html/2406.06025v1) describes 500 tests
    from 50 repos. Check the paper's GitHub for dataset access.
    """
    # TODO: Load actual RepoQA dataset
    print("TODO: Load RepoQA dataset")
    print("      Check https://arxiv.org/html/2406.06025v1 for dataset access")
    return []


def evaluate_answer(predicted: str, reference_func: str, reference_file: str) -> dict:
    """Check if the predicted function matches the reference.

    Evaluation criteria:
    - exact_match: predicted output contains the exact function name AND file path
    - func_match: predicted output contains the function name (partial credit)
    - file_match: predicted output mentions the correct file (partial credit)
    """
    pred_lower = predicted.lower()
    func_lower = reference_func.lower()
    file_lower = reference_file.lower()

    return {
        "exact_match": func_lower in pred_lower and file_lower in pred_lower,
        "func_match": func_lower in pred_lower,
        "file_match": file_lower in pred_lower,
    }


def run_task(task: dict, config_path: Path, workdir: Path, results_dir: Path) -> dict:
    """Run a single RepoQA task and return the result."""
    task_id = task.get("id", "unknown")
    description = task.get("description", "")
    reference_func = task.get("function_name", "")
    reference_file = task.get("file_path", "")
    repo = task.get("repo", "")

    print(f"\nTask: {task_id}")
    print(f"Repo: {repo}")
    print(f"Looking for: {reference_func} in {reference_file}")

    # TODO: Check out repo
    repo_dir = workdir  # placeholder

    # Write search prompt
    prompt_file = workdir / f"{task_id}_prompt.txt"
    prompt_file.write_text(
        f"Find the function in this codebase that matches the following description:\n\n"
        f"{description}\n\n"
        f"Return the exact function name and the file path where it is defined."
    )

    # Run Claude Code
    output_json = results_dir / f"{task_id}.json"
    subprocess.run(
        ["bash", str(RUN_ONE), str(config_path), str(repo_dir),
         str(prompt_file), str(output_json)],
        check=False,
    )

    # Read and evaluate
    if output_json.exists():
        with open(output_json) as f:
            result = json.load(f)
        predicted = result.get("result_text", "")
        result["evaluation"] = evaluate_answer(predicted, reference_func, reference_file)
    else:
        result = {"error": "No output produced"}

    result["task_id"] = task_id
    result["reference_func"] = reference_func
    result["reference_file"] = reference_file
    return result


def main():
    parser = argparse.ArgumentParser(description="Run RepoQA tasks")
    parser.add_argument("--config", required=True, help="Path to config JSON")
    parser.add_argument("--workdir", default=None, help="Working directory")
    parser.add_argument("--results-dir", default=None, help="Results directory")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    with open(config_path) as f:
        config = json.load(f)
    config_name = config["name"]

    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="repoqa_"))
    results_dir = Path(args.results_dir) if args.results_dir else PROJECT_ROOT / "results" / "repo_qa" / config_name
    results_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks()
    if not tasks:
        return

    print(f"Config: {config_name}, Tasks: {len(tasks)}")

    results = []
    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}]")
        result = run_task(task, config_path, workdir, results_dir)
        results.append(result)

    # Write summary
    completed = [r for r in results if "error" not in r]
    summary = {
        "config": config_name,
        "total_tasks": len(results),
        "completed": len(completed),
        "exact_match_rate": sum(
            1 for r in completed if r.get("evaluation", {}).get("exact_match")
        ) / max(len(completed), 1),
        "func_match_rate": sum(
            1 for r in completed if r.get("evaluation", {}).get("func_match")
        ) / max(len(completed), 1),
    }
    summary_path = results_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary: {json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()
