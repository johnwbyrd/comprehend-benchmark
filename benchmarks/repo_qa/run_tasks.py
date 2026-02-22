"""Run RepoQA tasks with Claude Code headless.

Usage:
    python run_tasks.py --config ../../configs/baseline.json
    python run_tasks.py --config ../../configs/comprehend.json
    python run_tasks.py --config ../../configs/comprehend.json --language python

RepoQA tests code search: given a natural-language description, find the
matching function in a repository.

Dataset: evalplus/repoqa on GitHub (not HuggingFace)
  - 500 tasks: 5 languages x 10 repos x 10 needle functions
  - Downloaded automatically from GitHub Releases as gzipped JSON
  - Each task: find a function from its natural-language description

This script:
1. Downloads and caches the RepoQA dataset
2. For each task, writes the repo files to a working directory
3. Runs Claude Code headless with the function description as prompt
4. Checks if the returned function matches the ground truth
"""

import argparse
import gzip
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RUN_ONE = PROJECT_ROOT / "scripts" / "run_one.sh"

REPOQA_URL = (
    "https://github.com/evalplus/repoqa_release/releases/download/"
    "2024-06-23/repoqa-2024-06-23.json.gz"
)
REPOQA_CACHE = PROJECT_ROOT / ".cache" / "repoqa-2024-06-23.json"


def download_dataset() -> dict:
    """Download and cache the RepoQA dataset."""
    if REPOQA_CACHE.exists():
        with open(REPOQA_CACHE) as f:
            return json.load(f)

    print(f"Downloading RepoQA dataset from {REPOQA_URL} ...")
    gz_path = REPOQA_CACHE.parent / "repoqa-2024-06-23.json.gz"
    REPOQA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(REPOQA_URL, gz_path)

    with gzip.open(gz_path, "rt") as f:
        data = json.load(f)

    with open(REPOQA_CACHE, "w") as f:
        json.dump(data, f)

    gz_path.unlink()
    print(f"Cached to {REPOQA_CACHE}")
    return data


def load_tasks(language_filter: str | None = None):
    """Load RepoQA tasks, flattened into a list of dicts.

    The raw dataset is nested: {language: [repos]}, each repo has {needles: [...]}.
    We flatten to one task per needle with fields matching what run_task expects.
    """
    dataset = download_dataset()

    tasks = []
    for language, repos in dataset.items():
        if language_filter and language != language_filter:
            continue
        for repo_obj in repos:
            repo_name = repo_obj["repo"]
            for needle in repo_obj.get("needles", []):
                tasks.append({
                    "id": f"{language}__{repo_name.replace('/', '__')}__{needle['name']}",
                    "language": language,
                    "repo": repo_name,
                    "function_name": needle["name"],
                    "file_path": needle["path"],
                    "description": needle["description"],
                    "repo_content": repo_obj.get("content", {}),
                })
    return tasks


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


def write_repo_files(repo_content: dict, repo_dir: Path):
    """Write the repo's file contents to disk so Claude can read them."""
    for file_path, content in repo_content.items():
        out_path = repo_dir / file_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, errors="replace")


def run_task(task: dict, config_path: Path, workdir: Path, results_dir: Path) -> dict:
    """Run a single RepoQA task and return the result."""
    task_id = task["id"]
    description = task["description"]
    reference_func = task["function_name"]
    reference_file = task["file_path"]
    repo = task["repo"]

    print(f"\nTask: {task_id}")
    print(f"Repo: {repo} ({task['language']})")
    print(f"Looking for: {reference_func} in {reference_file}")

    # Write repo files to a directory
    repo_dir = workdir / repo.replace("/", "__")
    if not repo_dir.exists():
        write_repo_files(task["repo_content"], repo_dir)
        # Init a git repo so Claude's git tools work
        subprocess.run(
            ["git", "init"], cwd=repo_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "add", "."], cwd=repo_dir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo_dir, check=True, capture_output=True,
            env={"GIT_AUTHOR_NAME": "bench", "GIT_AUTHOR_EMAIL": "bench@test",
                 "GIT_COMMITTER_NAME": "bench", "GIT_COMMITTER_EMAIL": "bench@test"},
        )

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
    parser.add_argument(
        "--language", default=None,
        choices=["python", "cpp", "java", "rust", "typescript"],
        help="Run only tasks for this language",
    )
    parser.add_argument("--workdir", default=None, help="Working directory")
    parser.add_argument("--results-dir", default=None, help="Results directory")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    with open(config_path) as f:
        config = json.load(f)
    config_name = config["name"]

    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="repoqa_"))
    default_results = PROJECT_ROOT / "results" / "repo_qa" / config_name
    results_dir = Path(args.results_dir) if args.results_dir else default_results
    results_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_tasks(language_filter=args.language)
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
