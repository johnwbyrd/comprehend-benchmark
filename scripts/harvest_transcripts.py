#!/usr/bin/env python3
"""
Harvest Claude Code session transcripts from ~/.claude/projects/ into the
project's runs/ directory, renaming from session UUID to instance ID.

Usage:
    python scripts/harvest_transcripts.py [--claude-projects-dir DIR]

Reads result JSONs from runs/swebench_lite/{baseline,comprehend}/results/,
extracts session_id and repo_dir, finds the matching transcript in the Claude
Code projects directory, and copies it into runs/swebench_lite/{config}/transcripts/.

Safe to run multiple times — skips files that already exist at the destination.
Never deletes or moves source files.
"""

import argparse
import json
import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def repo_dir_to_claude_projects_name(repo_dir: str) -> str:
    """Convert an absolute repo path to the Claude Code projects directory name.

    Claude Code converts /tmp/swebench_iu299bow/matplotlib__matplotlib to
    -tmp-swebench-iu299bow-matplotlib--matplotlib by replacing all / and _ with -.

    >>> repo_dir_to_claude_projects_name("/tmp/swebench_iu299bow/matplotlib__matplotlib")
    '-tmp-swebench-iu299bow-matplotlib--matplotlib'
    """
    return repo_dir.replace("/", "-").replace("_", "-")


def find_claude_projects_dir(repo_dir: str, claude_base: Path) -> Path | None:
    """Find the Claude Code projects directory for a given repo_dir path."""
    dir_name = repo_dir_to_claude_projects_name(repo_dir)
    candidate = claude_base / dir_name
    if candidate.is_dir():
        return candidate
    return None


def harvest(runs_dir: Path, claude_base: Path) -> dict:
    """Harvest transcripts for all configs. Returns stats dict."""
    stats = {"found": 0, "skipped": 0, "missing": 0, "errors": [], "unmapped": []}

    for config in ["baseline", "comprehend"]:
        results_dir = runs_dir / config / "results"
        transcripts_dir = runs_dir / config / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)

        if not results_dir.is_dir():
            print(f"  WARNING: {results_dir} does not exist, skipping")
            continue

        for result_file in sorted(results_dir.glob("*.json")):
            instance_id = result_file.stem
            try:
                with open(result_file) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                stats["errors"].append(f"{instance_id}: {e}")
                continue

            session_id = data.get("session_id", "")
            if not session_id:
                stats["errors"].append(f"{instance_id}: no session_id in result JSON")
                continue

            repo_dir = data.get("repo_dir", "")
            if not repo_dir:
                stats["errors"].append(f"{instance_id}: no repo_dir in result JSON")
                continue

            projects_dir = find_claude_projects_dir(repo_dir, claude_base)
            if projects_dir is None:
                stats["missing"] += 1
                stats["errors"].append(f"{instance_id}: projects dir not found for {repo_dir}")
                continue

            # Copy main transcript
            src_jsonl = projects_dir / f"{session_id}.jsonl"
            dst_jsonl = transcripts_dir / f"{instance_id}.jsonl"

            if dst_jsonl.exists():
                stats["skipped"] += 1
            elif src_jsonl.exists():
                shutil.copy2(src_jsonl, dst_jsonl)
                stats["found"] += 1
                size_kb = dst_jsonl.stat().st_size / 1024
                print(f"  {config}/{instance_id}.jsonl ({size_kb:.0f} KB)")
            else:
                stats["missing"] += 1
                stats["errors"].append(f"{instance_id}: transcript {session_id}.jsonl not found")
                continue

            # Copy subagent directory if it exists
            src_subagent_dir = projects_dir / session_id
            if src_subagent_dir.is_dir():
                dst_subagent_dir = transcripts_dir / instance_id
                if not dst_subagent_dir.exists():
                    shutil.copytree(src_subagent_dir, dst_subagent_dir)
                    print(f"  {config}/{instance_id}/  (subagents)")

    # Find unmapped transcripts (sessions not linked to any result JSON)
    mapped_sessions = set()
    repo_dirs_seen = set()
    for config in ["baseline", "comprehend"]:
        results_dir = runs_dir / config / "results"
        if not results_dir.is_dir():
            continue
        for result_file in results_dir.glob("*.json"):
            try:
                with open(result_file) as f:
                    data = json.load(f)
                sid = data.get("session_id", "")
                rd = data.get("repo_dir", "")
                if sid:
                    mapped_sessions.add(sid)
                if rd:
                    repo_dirs_seen.add(rd)
            except (json.JSONDecodeError, OSError):
                pass

    for repo_dir in repo_dirs_seen:
        projects_dir = find_claude_projects_dir(repo_dir, claude_base)
        if projects_dir is None:
            continue
        for jsonl_file in projects_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            if session_id not in mapped_sessions:
                repo_name = repo_dir_to_claude_projects_name(repo_dir)
                stats["unmapped"].append((repo_name, session_id, jsonl_file))

    if stats["unmapped"]:
        unmapped_dir = runs_dir / "unmapped"
        unmapped_dir.mkdir(parents=True, exist_ok=True)
        for repo, session_id, src in stats["unmapped"]:
            dst = unmapped_dir / f"{repo}_{session_id}.jsonl"
            if not dst.exists():
                shutil.copy2(src, dst)
                print(f"  unmapped/{dst.name}")

    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--claude-projects-dir",
        default=os.path.expanduser("~/.claude/projects"),
        help="Base directory for Claude Code project sessions (default: ~/.claude/projects)",
    )
    args = parser.parse_args()

    runs_dir = PROJECT_ROOT / "runs" / "swebench_lite"
    claude_base = Path(args.claude_projects_dir)

    print(f"Runs directory:  {runs_dir}")
    print(f"Claude projects: {claude_base}")
    print()

    stats = harvest(runs_dir, claude_base)

    print()
    print(f"Transcripts copied:  {stats['found']}")
    print(f"Already present:     {stats['skipped']}")
    print(f"Missing:             {stats['missing']}")
    print(f"Unmapped sessions:   {len(stats['unmapped'])}")

    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats["errors"]:
            print(f"  {err}")

    # Print total size
    total_size = 0
    for config in ["baseline", "comprehend"]:
        t_dir = runs_dir / config / "transcripts"
        if t_dir.is_dir():
            for f in t_dir.rglob("*"):
                if f.is_file():
                    total_size += f.stat().st_size
    unmapped_dir = runs_dir / "unmapped"
    if unmapped_dir.is_dir():
        for f in unmapped_dir.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size

    print(f"\nTotal transcript size: {total_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
