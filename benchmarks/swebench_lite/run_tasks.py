"""Run SWE-bench Lite tasks with Claude Code headless.

Usage:
    python run_tasks.py --config ../../configs/baseline.json
    python run_tasks.py --config ../../configs/comprehend.json --all
    python run_tasks.py --config ../../configs/baseline.json --instance-id astropy__astropy-12907

This script:
1. Loads the SWE-bench Lite dataset
2. For each task, checks out the repo at the base commit
3. Runs Claude Code headless with the issue as the prompt
4. Captures the resulting git diff as the prediction
5. Writes predictions in SWE-bench JSONL format
"""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from datasets import load_dataset

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RUN_ONE = PROJECT_ROOT / "scripts" / "run_one.sh"
SAMPLE_TASKS = SCRIPT_DIR / "sample_tasks.json"


def load_tasks(use_all: bool, instance_id: str | None = None, repos: list[str] | None = None):
    """Load SWE-bench Lite tasks from HuggingFace.

    Dataset: princeton-nlp/SWE-bench_Lite (test split, 300 tasks)
    Fields: instance_id, repo, base_commit, problem_statement, patch, test_patch, ...
    """
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    if instance_id:
        return [t for t in dataset if t["instance_id"] == instance_id]

    if repos:
        return [t for t in dataset if t["repo"] in repos]

    if not use_all:
        with open(SAMPLE_TASKS) as f:
            sample_ids = set(json.load(f))
        return [t for t in dataset if t["instance_id"] in sample_ids]

    return list(dataset)


def checkout_repo(task: dict, workdir: Path) -> Path:
    """Clone and checkout the repo at the base commit.

    TODO: Implement caching so repos aren't re-cloned for every task.
    """
    repo = task["repo"]
    base_commit = task["base_commit"]
    repo_dir = workdir / repo.replace("/", "__")

    if not repo_dir.exists():
        subprocess.run(
            ["git", "clone", f"https://github.com/{repo}.git", str(repo_dir)],
            check=True,
            capture_output=True,
        )

    # Reset any changes left by a previous task
    subprocess.run(
        ["git", "checkout", "."],
        cwd=repo_dir,
        check=False,
        capture_output=True,
    )

    subprocess.run(
        ["git", "checkout", base_commit],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "clean", "-fdx"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    return repo_dir


def run_task(task: dict, config_path: Path, workdir: Path, results_dir: Path) -> dict:
    """Run a single SWE-bench task and return the result."""
    instance_id = task["instance_id"]
    print(f"\n{'='*60}")
    print(f"Task: {instance_id}")
    print(f"{'='*60}")

    # Check out repo
    repo_dir = checkout_repo(task, workdir)

    # Write prompt to temp file
    prompt_file = workdir / f"{instance_id}_prompt.txt"
    prompt_file.write_text(task["problem_statement"], encoding="utf-8")

    # Run Claude Code
    output_json = results_dir / f"{instance_id}.json"
    subprocess.run(
        ["bash", str(RUN_ONE), str(config_path), str(repo_dir),
         str(prompt_file), str(output_json)],
        check=False,  # Don't fail the whole run if one task errors
    )

    # Read result
    if output_json.exists():
        with open(output_json) as f:
            result = json.load(f)
    else:
        result = {"error": "No output produced", "instance_id": instance_id}

    result["instance_id"] = instance_id
    return result


def write_predictions(results: list[dict], output_path: Path, config_name: str):
    """Write results in SWE-bench predictions JSONL format."""
    with open(output_path, "w") as f:
        for r in results:
            prediction = {
                "instance_id": r["instance_id"],
                "model_name_or_path": f"claude-code-{config_name}",
                "model_patch": r.get("git_diff", ""),
            }
            f.write(json.dumps(prediction) + "\n")
    print(f"\nPredictions written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Run SWE-bench Lite tasks")
    parser.add_argument("--config", required=True, help="Path to config JSON")
    parser.add_argument(
        "--all", action="store_true", help="Run all 300 tasks (default: curated subset)"
    )
    parser.add_argument("--instance-id", help="Run a single specific task")
    parser.add_argument(
        "--repo", action="append", dest="repos",
        help="Filter to tasks from this repo (repeatable, e.g. --repo mwaskom/seaborn --repo pylint-dev/pylint)"
    )
    parser.add_argument("--workdir", default=None, help="Working directory for repo checkouts")
    parser.add_argument("--results-dir", default=None, help="Directory for result JSON files")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    with open(config_path) as f:
        config = json.load(f)
    config_name = config["name"]

    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="swebench_"))
    default_results = PROJECT_ROOT / "results" / "swebench_lite" / config_name
    results_dir = Path(args.results_dir) if args.results_dir else default_results
    results_dir.mkdir(parents=True, exist_ok=True)

    print(f"Config:     {config_name}")
    print(f"Work dir:   {workdir}")
    print(f"Results:    {results_dir}")

    tasks = load_tasks(use_all=args.all, instance_id=args.instance_id, repos=args.repos)
    if not tasks:
        print("No tasks loaded. See TODO comments in load_tasks().")
        return

    print(f"Tasks:      {len(tasks)}")

    results = []
    skipped = 0
    for i, task in enumerate(tasks, 1):
        instance_id = task["instance_id"]
        existing = results_dir / f"{instance_id}.json"
        if existing.exists():
            print(f"\n[{i}/{len(tasks)}] Skipping {instance_id} (result exists)")
            with open(existing) as f:
                results.append(json.load(f))
            skipped += 1
            continue
        print(f"\n[{i}/{len(tasks)}]")
        result = run_task(task, config_path, workdir, results_dir)
        results.append(result)

    if skipped:
        print(f"\nSkipped {skipped} tasks with existing results (delete JSON to re-run)")

    # Rebuild predictions JSONL from all per-task JSONs in results_dir
    # so that successive single-task runs accumulate correctly
    all_results = []
    for result_file in sorted(results_dir.glob("*.json")):
        if result_file.name == "summary.json":
            continue
        with open(result_file) as f:
            r = json.load(f)
        if "instance_id" not in r:
            r["instance_id"] = result_file.stem
        all_results.append(r)

    predictions_path = results_dir / "predictions.jsonl"
    write_predictions(all_results, predictions_path, config_name)

    # Write summary covering all accumulated results
    summary_path = results_dir / "summary.json"
    summary = {
        "config": config_name,
        "total_tasks": len(all_results),
        "completed": sum(1 for r in all_results if "error" not in r),
        "errors": sum(1 for r in all_results if "error" in r),
        "total_wall_time": sum(r.get("wall_time_seconds", 0) for r in all_results),
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary: {json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()
