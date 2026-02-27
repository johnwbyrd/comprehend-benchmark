#!/usr/bin/env bash
#
# Run a single task with Claude Code headless and capture results.
#
# Usage:
#   run_one.sh <config_json> <repo_dir> <prompt_file> <output_json> [transcript_dir]
#
# Arguments:
#   config_json    - Path to configs/baseline.json or configs/comprehend.json
#   repo_dir       - Path to the git repository (already checked out at the right commit)
#   prompt_file    - Path to a file containing the task prompt
#   output_json    - Path to write the combined result JSON
#   transcript_dir - (Optional) Directory to copy the session transcript into
#
# Prerequisites:
#   - claude CLI on PATH with ANTHROPIC_API_KEY set
#   - python on PATH (python3 or python)
#   - git installed
#
# The script:
#   1. Installs/removes the comprehend skill based on config
#   2. Runs Claude Code headless with the task prompt
#   3. Captures git diff (for patch-based benchmarks)
#   4. Writes a combined result JSON with metrics

set -euo pipefail

# --- Find Python (python3 on Linux/macOS, python on Windows) ---
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "ERROR: python not found on PATH"
    exit 1
fi

if [ $# -lt 4 ] || [ $# -gt 5 ]; then
    echo "Usage: $0 <config_json> <repo_dir> <prompt_file> <output_json> [transcript_dir]"
    exit 1
fi

CONFIG_JSON="$1"
REPO_DIR="$2"
PROMPT_FILE="$3"
OUTPUT_JSON="$4"
TRANSCRIPT_DIR="${5:-}"

# --- Parse config with Python (no jq dependency) ---
read_config() {
    $PYTHON -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get(sys.argv[2],'') or '')" "$CONFIG_JSON" "$1"
}

CONFIG_NAME=$(read_config name)
ALLOWED_TOOLS=$(read_config allowed_tools)
MAX_TURNS=$(read_config max_turns)
MODEL=$(read_config model)
APPEND_PROMPT=$(read_config append_system_prompt)
SKILLS_DIR=$(read_config skills_dir)

echo "=== Running task ==="
echo "Config: $CONFIG_NAME"
echo "Repo:   $REPO_DIR"
echo "Output: $OUTPUT_JSON"

# --- Set up skills directory ---
CLAUDE_DIR="$REPO_DIR/.claude"
if [ -n "$SKILLS_DIR" ]; then
    echo "Installing comprehend skill..."
    mkdir -p "$CLAUDE_DIR/skills"
    COMPREHEND_SRC="${COMPREHEND_SRC:-$HOME/git/comprehend/skills/comprehend}"
    if [ ! -d "$COMPREHEND_SRC" ]; then
        echo "ERROR: comprehend skill not found at $COMPREHEND_SRC"
        echo "       Set COMPREHEND_SRC to the path of your comprehend skill directory"
        exit 1
    fi
    cp -r "$COMPREHEND_SRC" "$CLAUDE_DIR/skills/"
else
    echo "Baseline config: no skills installed"
    rm -rf "$CLAUDE_DIR/skills"
fi

# --- Read prompt ---
PROMPT=$(cat "$PROMPT_FILE")

# --- Run Claude Code ---
START_TIME=$(date +%s)

CLAUDE_OUTPUT_FILE=$(mktemp)
CLAUDE_STDERR_FILE=$(mktemp)
GIT_DIFF_FILE=$(mktemp)
trap 'rm -f "$CLAUDE_OUTPUT_FILE" "$CLAUDE_STDERR_FILE" "$GIT_DIFF_FILE"' EXIT

cd "$REPO_DIR"

unset CLAUDECODE
claude -p "$PROMPT" \
    --output-format json \
    --allowedTools "$ALLOWED_TOOLS" \
    --max-turns "$MAX_TURNS" \
    --model "$MODEL" \
    --append-system-prompt "$APPEND_PROMPT" \
    > "$CLAUDE_OUTPUT_FILE" 2>"$CLAUDE_STDERR_FILE" || true

# If claude produced no output, something went wrong — don't write a bogus result
if [ ! -s "$CLAUDE_OUTPUT_FILE" ]; then
    echo "ERROR: claude produced no output" >&2
    echo "Stderr: $(cat "$CLAUDE_STDERR_FILE")" >&2
    exit 1
fi

END_TIME=$(date +%s)
WALL_TIME=$((END_TIME - START_TIME))

# --- Capture git diff ---
git diff > "$GIT_DIFF_FILE" 2>/dev/null || true

# --- Build result JSON safely via Python reading from temp files ---
mkdir -p "$(dirname "$OUTPUT_JSON")"

$PYTHON - "$CONFIG_NAME" "$REPO_DIR" "$WALL_TIME" \
    "$CLAUDE_OUTPUT_FILE" "$GIT_DIFF_FILE" "$OUTPUT_JSON" <<'PYEOF'
import json
import sys

config_name = sys.argv[1]
repo_dir = sys.argv[2]
wall_time = int(sys.argv[3])
claude_output_path = sys.argv[4]
git_diff_path = sys.argv[5]
output_path = sys.argv[6]

with open(claude_output_path) as f:
    raw = f.read().strip()
try:
    claude_data = json.loads(raw) if raw else {}
except json.JSONDecodeError:
    claude_data = {"raw_output": raw}

with open(git_diff_path) as f:
    git_diff = f.read()

result = {
    "config": config_name,
    "repo_dir": repo_dir,
    "wall_time_seconds": wall_time,
    "git_diff": git_diff,
    "claude_output": claude_data,
    "session_id": claude_data.get("session_id", ""),
    "result_text": claude_data.get("result", ""),
    "total_cost_usd": claude_data.get("total_cost_usd", 0),
    "num_turns": claude_data.get("num_turns", 0),
}

with open(output_path, "w") as f:
    json.dump(result, f, indent=2)

print(f"Done: {wall_time}s, saved to {output_path}")
PYEOF

# --- Copy session transcript if transcript_dir is set ---
if [ -n "$TRANSCRIPT_DIR" ]; then
    SESSION_ID=$($PYTHON -c "import json; d=json.load(open('$OUTPUT_JSON')); print(d.get('session_id',''))")
    if [ -n "$SESSION_ID" ]; then
        # Claude Code projects dir: absolute repo path with / and _ replaced by -
        CLAUDE_PROJ_NAME=$(echo "$REPO_DIR" | sed 's|[/_]|-|g')
        CLAUDE_PROJ_DIR="$HOME/.claude/projects/$CLAUDE_PROJ_NAME"
        INSTANCE_ID=$(basename "$OUTPUT_JSON" .json)

        mkdir -p "$TRANSCRIPT_DIR"

        # Copy main transcript
        if [ -f "$CLAUDE_PROJ_DIR/$SESSION_ID.jsonl" ]; then
            cp "$CLAUDE_PROJ_DIR/$SESSION_ID.jsonl" "$TRANSCRIPT_DIR/$INSTANCE_ID.jsonl"
            echo "Transcript saved: $TRANSCRIPT_DIR/$INSTANCE_ID.jsonl"
        else
            echo "WARNING: transcript not found at $CLAUDE_PROJ_DIR/$SESSION_ID.jsonl"
        fi

        # Copy subagent directory if it exists
        if [ -d "$CLAUDE_PROJ_DIR/$SESSION_ID" ]; then
            cp -r "$CLAUDE_PROJ_DIR/$SESSION_ID" "$TRANSCRIPT_DIR/$INSTANCE_ID"
            echo "Subagent data saved: $TRANSCRIPT_DIR/$INSTANCE_ID/"
        fi
    else
        echo "WARNING: no session_id in result, cannot capture transcript"
    fi
fi
