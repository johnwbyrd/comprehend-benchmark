"""Run SWE-QA tasks with Claude Code headless.

Usage:
    python run_tasks.py --config ../../configs/baseline.json
    python run_tasks.py --config ../../configs/comprehend.json

SWE-QA tests code comprehension, not editing. Each task asks a question
about a repository and expects a factual answer.

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
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
RUN_ONE = PROJECT_ROOT / "scripts" / "run_one.sh"


def load_tasks():
    """Load SWE-QA tasks.

    TODO: Replace with actual dataset loading once the dataset is available.
    The SWE-QA paper (arxiv.org/abs/2509.14635) describes 576 Q&A pairs.
    Check the paper's GitHub repo for download instructions.
    """
    # from datasets import load_dataset
    # ds = load_dataset("swe-qa/SWE-QA", split="test")
    # return list(ds)

    print("TODO: Load SWE-QA dataset")
    print("      Check https://arxiv.org/abs/2509.14635 for dataset access")
    return []


def evaluate_answer(predicted: str, reference: str) -> dict:
    """Evaluate a predicted answer against the reference.

    TODO: Implement LLM-as-judge evaluation. The basic approach:
    1. Send both answers to Claude with a scoring prompt
    2. Ask it to rate correctness (1-5) and completeness (1-5)
    3. Return structured scores

    For now, returns a placeholder.
    """
    # Simple heuristic: check if key terms from reference appear in prediction
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
    task_id = task.get("id", "unknown")
    question = task.get("question", "")
    reference = task.get("answer", "")
    repo = task.get("repo", "")

    print(f"\nTask: {task_id}")
    print(f"Repo: {repo}")
    print(f"Q:    {question[:80]}...")

    # TODO: Check out repo at the correct commit
    # repo_dir = checkout_repo(task, workdir)
    repo_dir = workdir  # placeholder

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
    parser.add_argument("--workdir", default=None, help="Working directory")
    parser.add_argument("--results-dir", default=None, help="Results directory")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    with open(config_path) as f:
        config = json.load(f)
    config_name = config["name"]

    workdir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="sweqa_"))
    results_dir = Path(args.results_dir) if args.results_dir else PROJECT_ROOT / "results" / "swe_qa" / config_name
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
