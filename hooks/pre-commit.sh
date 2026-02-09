#!/bin/bash
# Pre-Commit hook for multi-review plugin
#
# Triggered before git commit
#
# Usage (via hook): Automatic
# Usage (manual): bash pre-commit.sh [--strict] [--silent]
#
# Exit codes:
#   0: Pass - review passed or warnings only
#   1: Fail - critical issues found (blocks commit in strict mode)
#   2: Error - review failed to run

set -euo pipefail

# Plugin root
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Python script
PRE_COMMIT_SCRIPT="${PLUGIN_ROOT}/scripts/pre_commit_check.py"

# Default arguments
STRICT=""
SILENT=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --strict)
            STRICT="--strict"
            shift
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
if [[ ! -f "$PRE_COMMIT_SCRIPT" ]]; then
    echo "[ERROR] pre_commit_check.py not found at: $PRE_COMMIT_SCRIPT" >&2
    exit 2
fi

# Check if in git repo
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "[WARNING] Not in a git repository" >&2
    exit 0
fi

# Build command
CMD=("python3" "$PRE_COMMIT_SCRIPT")

if [[ -n "$STRICT" ]]; then
    CMD+=("$STRICT")
fi

if [[ -n "$SILENT" ]]; then
    CMD+=("$SILENT")
fi

# Run the review
"${CMD[@]}"
exit_code=$?

# Exit with the script's exit code
exit $exit_code
