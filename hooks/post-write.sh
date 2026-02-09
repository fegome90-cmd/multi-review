#!/bin/bash
# Post-Write hook for multi-review plugin
#
# Triggered after Write/Edit operations in Claude Code
#
# Usage (via hook): Automatic
# Usage (manual): bash post-write.sh [--file PATH] [--silent]
#
# Exit codes:
#   0: No issues found
#   1: Issues found
#   2: Error occurred

set -euo pipefail

# Plugin root
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Python script
AUTO_REVIEW_SCRIPT="${PLUGIN_ROOT}/scripts/auto_review.py"

# Default arguments
FILE_PATH=""
SILENT=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --file)
            FILE_PATH="$2"
            shift 2
            ;;
        --silent)
            SILENT="--silent"
            shift
            ;;
        *)
            # Unknown argument - might be from tool input
            FILE_PATH="$1"
            shift
            ;;
    esac
done

# Check if Python script exists
if [[ ! -f "$AUTO_REVIEW_SCRIPT" ]]; then
    echo "[ERROR] auto_review.py not found at: $AUTO_REVIEW_SCRIPT" >&2
    exit 2
fi

# Build command
CMD=("python3" "$AUTO_REVIEW_SCRIPT")

if [[ -n "$FILE_PATH" ]]; then
    CMD+=("--file" "$FILE_PATH")
fi

if [[ -n "$SILENT" ]]; then
    CMD+=("$SILENT")
fi

# Run the review
"${CMD[@]}"
exit_code=$?

# Exit with the script's exit code
exit $exit_code
