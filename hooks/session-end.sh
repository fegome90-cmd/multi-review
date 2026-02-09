#!/bin/bash
# Session-End hook for multi-review plugin
#
# Triggered at Claude Code session end
#
# Usage (via hook): Automatic
# Usage (manual): bash session-end.sh [--context PATH] [--silent]
#
# Exit codes:
#   0: Success
#   1: Issues found
#   2: Error

set -euo pipefail

# Plugin root
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Python script
SESSION_REVIEW_SCRIPT="${PLUGIN_ROOT}/scripts/session_review.py"

# Default arguments
CONTEXT_PATH=""
SILENT=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --context)
            CONTEXT_PATH="$2"
            shift 2
            ;;
        --silent)
            SILENT="--silent"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Check if Python script exists
if [[ ! -f "$SESSION_REVIEW_SCRIPT" ]]; then
    echo "[ERROR] session_review.py not found at: $SESSION_REVIEW_SCRIPT" >&2
    exit 2
fi

# Build command
CMD=("python3" "$SESSION_REVIEW_SCRIPT")

if [[ -n "$CONTEXT_PATH" ]]; then
    CMD+=("--context" "$CONTEXT_PATH")
fi

if [[ -n "$SILENT" ]]; then
    CMD+=("$SILENT")
fi

# Run the review
"${CMD[@]}"
exit_code=$?

# Exit with the script's exit code
exit $exit_code
