"""Run SWE-QA tasks with Claude Code headless.

Usage:
    python run_tasks.py --config ../../configs/baseline.json
    python run_tasks.py --config ../../configs/comprehend.json
    python run_tasks.py --config ../../configs/comprehend.json --repo django

SWE-QA tests code comprehension, not editing. Each task asks a question
about a repository and expects a factual answer.

Dataset: swe-qa/SWE-QA-Benchmark on HuggingFace
  - 720 question-answer pairs across 15 repos (48 per repo)
  - Fields per row: question, answer
  - Repo identity comes from the split name (django, flask, pytest, etc.)

This script:
1. Loads the SWE-QA dataset
2. For each task, checks out the repo
3. Runs Claude Code headless with the question as the prompt
4. Captures the answer text
5. Evaluates against the reference answer
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

# Maps SWE-QA split names to GitHub repo URLs for checkout
REPO_MAP = {
    "astropy": "astropy/astropy",
    "django": "django/django",
    "flask": "pallets/flask",
    "matplotlib": "matplotlib/matplotlib",
    "pylint": "pylint-dev/pylint",
    "pytest": "pytest-dev/pytest",
    "requests": "psf/requests",
    "scikit_learn": "scikit-learn/scikit-learn",
    "sphinx": "sphinx-doc/sphinx",
    "sqlfluff": "sqlfluff/sqlfluff",
    "sympy": "sympy/sympy",
    "xarray": "pydata/xarray",
    "conan": "conan-io/conan",
    "streamlink": "streamlink/streamlink",
    "reflex": "reflex-dev/reflex",
}


def load_tasks(repo_filter: str | None = None):
    """Load SWE-QA tasks from HuggingFace.

    Dataset: swe-qa/SWE-QA-Benchmark
    Each split is a repo name with 48 question-answer pairs.
    The 'default' split contains all 720.
    """
    if repo_filter:
        ds = load_dataset("swe-qa/SWE-QA-Benchmark", split=repo_filter)
        tasks = []
        for i, row in enumerate(ds):
            tasks.append({
                "id": f"{repo_filter}_{i:03d}",
                "repo": REPO_MAP.get(repo_filter, repo_filter),
                "repo_split": repo_filter,
                "question": row["question"],
                "answer": row["answer"],
            })
        return tasks

    # Load all repos
    tasks = []
    for split_name, github_repo in REPO_MAP.items():
        try:
            ds = load_dataset("swe-qa/SWE-QA-Benchmark", split=split_name)
        except ValueError:
            continue
        for i, row in enumerate(ds):
            tasks.append({
                "id": f"{split_name}_{i:03d}",
                "repo": github_repo,
                "repo_split": split_name,
                "question": row["question"],
                "answer": row["answer"],
            })
    return tasks


def evaluate_answer(predicted: str, reference: str) -> dict:
    """Evaluate a predicted answer against the reference.

    Returns word overlap as a baseline metric. LLM-as-judge scoring
    can be added later for correctness and completeness (1-5 scale).
    """
    ref_words = set(reference.lower().split())
    pred_words = set(predicted.lower().split())
    overlap = len(ref_words & pred_words) / max(len(ref_words), 1)

    return {
        "word_overlap": round(overlap, 3),
        "correctness": None,   # TODO: LLM-as-judge score (1-5)
        "completeness": None,  # TODO: LLM-as-judge score (1-5)
    }


def run_task(task: dict, config_path: Path, workdir: Path, results_dir: Path) -> dict:
    """Run a single SWE-QA task and return the result."""
    task_id = task["id"]
    question = task["question"]
    reference = task["answer"]
    repo = task["repo"]

    print(f"\nTask: {task_id}")
    print(f"Repo: {repo}")
    print(f"Q:    {question[:80]}...")

    # Clone the repo if needed (SWE-QA doesn't specify commits, use default branch)
    repo_dir = workdir / repo.replace("/", "__")
    if not repo_dir.exists():
        subprocess.run(
            ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", str(repo_dir)],
            check=True,
            capture_output=True,
        )

    # Write question as prompt
    prompt_file = workdir / f"{task_id}_prompt.txt"
    prompt_file.write_text(
        f"Answer this question about the codebase:\n\n{question}\n\n"
        f"Be specific and reference exact file paths and function names."
    )

    # Run Claude Code
    output_json = results_dir / f"{task_id}.json"
    subprocess.run(
        ["bash", str(RUN_ONE), str(config_path), str(repo_dir),
         str(prompt_file), str(output_json)],
        check=False,
    )

    # Read and evaluate result
    if output_json.exists():
        with open(output_json) as f:
            result = json.load(f)
        predicted = result.get("result_text", "")
        result["evaluation"] = evaluate_answer(predicted, reference)
    else:
        result = {"error": "No output produced"}

    result["task_id"] = task_id
    result["reference_answer"] = reference
    return result


def main():
    parser = argparse.ArgumentParser(description="Run SWE-QA tasks")
    parser.add_argument("--config", required=True, help="Path to config JSON")
    parser.add_argument("--repo", default=None, help="Run only tasks for this repo split name")
    parser.add_argument("--workdir", default=None, help="Working directory")
    parser.add_argument("--results-dir", default=None, help="Results directory")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    with open(config_path) as f:
        config = json.load(f)
    config_name = config["name"]

    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="sweqa_"))
    default_results = PROJECT_ROOT / "results" / "swe_qa" / config_name
    results_dir = Path(args.results_dir) if args.results_dir else default_results
    results_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(repo_filter=args.repo)
    if not tasks:
        print("No tasks loaded.")
        return

    print(f"Config: {config_name}, Tasks: {len(tasks)}")

    results = []
    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}]")
        result = run_task(task, config_path, workdir, results_dir)
        results.append(result)

    # Write summary
    summary = {
        "config": config_name,
        "total_tasks": len(results),
        "completed": sum(1 for r in results if "error" not in r),
        "avg_word_overlap": sum(
            r.get("evaluation", {}).get("word_overlap", 0) for r in results
        ) / max(len(results), 1),
    }
    summary_path = results_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary: {json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()
