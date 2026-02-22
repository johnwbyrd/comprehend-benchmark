#!/usr/bin/env bash
#
# Run a single task with Claude Code headless and capture results.
#
# Usage:
#   run_one.sh <config_json> <repo_dir> <prompt_file> <output_json>
#
# Arguments:
#   config_json  - Path to configs/baseline.json or configs/comprehend.json
#   repo_dir     - Path to the git repository (already checked out at the right commit)
#   prompt_file  - Path to a file containing the task prompt
#   output_json  - Path to write the combined result JSON
#
# The script:
#   1. Installs/removes the comprehend skill based on config
#   2. Runs Claude Code headless with the task prompt
#   3. Captures git diff (for patch-based benchmarks)
#   4. Writes a combined result JSON with metrics

set -euo pipefail

if [ $# -ne 4 ]; then
    echo "Usage: $0 <config_json> <repo_dir> <prompt_file> <output_json>"
    exit 1
fi

CONFIG_JSON="$1"
REPO_DIR="$2"
PROMPT_FILE="$3"
OUTPUT_JSON="$4"

# --- Parse config ---
# TODO: Install jq or use python for JSON parsing if jq is not available
CONFIG_NAME=$(jq -r '.name' "$CONFIG_JSON")
ALLOWED_TOOLS=$(jq -r '.allowed_tools' "$CONFIG_JSON")
MAX_TURNS=$(jq -r '.max_turns' "$CONFIG_JSON")
MODEL=$(jq -r '.model' "$CONFIG_JSON")
APPEND_PROMPT=$(jq -r '.append_system_prompt' "$CONFIG_JSON")
SKILLS_DIR=$(jq -r '.skills_dir // empty' "$CONFIG_JSON")

echo "=== Running task ==="
echo "Config: $CONFIG_NAME"
echo "Repo:   $REPO_DIR"
echo "Output: $OUTPUT_JSON"

# --- Set up skills directory ---
CLAUDE_DIR="$REPO_DIR/.claude"
if [ -n "$SKILLS_DIR" ]; then
    echo "Installing comprehend skill..."
    mkdir -p "$CLAUDE_DIR/skills"
    # TODO: Adjust this path to where comprehend is installed on your system
    COMPREHEND_SRC="${COMPREHEND_SRC:-$HOME/git/comprehend/skills/comprehend}"
    cp -r "$COMPREHEND_SRC" "$CLAUDE_DIR/skills/"
else
    echo "Baseline config: no skills installed"
    rm -rf "$CLAUDE_DIR/skills"
fi

# --- Read prompt ---
PROMPT=$(cat "$PROMPT_FILE")

# --- Run Claude Code ---
START_TIME=$(date +%s)

cd "$REPO_DIR"

# TODO: Ensure 'claude' is on your PATH and ANTHROPIC_API_KEY is set
CLAUDE_OUTPUT=$(claude -p "$PROMPT" \
    --output-format json \
    --allowedTools "$ALLOWED_TOOLS" \
    --max-turns "$MAX_TURNS" \
    --model "$MODEL" \
    --append-system-prompt "$APPEND_PROMPT" \
    2>/dev/null) || true

END_TIME=$(date +%s)
WALL_TIME=$((END_TIME - START_TIME))

# --- Capture git diff ---
GIT_DIFF=$(git diff 2>/dev/null || echo "")

# --- Build result JSON ---
# TODO: Extract token counts from CLAUDE_OUTPUT (field names may vary by CLI version)
mkdir -p "$(dirname "$OUTPUT_JSON")"

python3 -c "
import json, sys

claude_output = '''$CLAUDE_OUTPUT'''
try:
    claude_data = json.loads(claude_output) if claude_output.strip() else {}
except json.JSONDecodeError:
    claude_data = {'raw_output': claude_output}

result = {
    'config': '$CONFIG_NAME',
    'repo_dir': '$REPO_DIR',
    'wall_time_seconds': $WALL_TIME,
    'git_diff': '''$(echo "$GIT_DIFF" | python3 -c "import sys; print(sys.stdin.read().replace('\\\\','\\\\\\\\').replace(\"'''\",\"''\" + \"'\"))" 2>/dev/null || echo "")''',
    'claude_output': claude_data,
    'session_id': claude_data.get('session_id', ''),
    'result_text': claude_data.get('result', ''),
    'total_cost_usd': claude_data.get('cost_usd', 0),
    'total_tokens': claude_data.get('num_turns', 0),  # TODO: map to actual token field
}

with open('$OUTPUT_JSON', 'w') as f:
    json.dump(result, f, indent=2)

print(f'Done: {result[\"wall_time_seconds\"]}s, saved to $OUTPUT_JSON')
"
