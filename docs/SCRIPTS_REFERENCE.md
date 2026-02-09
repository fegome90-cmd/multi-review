# Scripts Reference

Complete reference for all standalone Python scripts in the `multi-review` plugin.

## Overview

All scripts are standalone executables that use only Python 3.10+ standard library. They can be run independently or called via hooks.

| Script | Purpose | Exit Codes |
|--------|---------|------------|
| `context_detector.py` | Context detection & agent suggestions | 0=success, 1=issues, 2=error |
| `auto_review.py` | Post-Write review handler | 0=success, 1=issues, 2=error |
| `pre_commit_check.py` | Pre-Commit review handler | 0=success, 1=issues, 2=error |
| `session_review.py` | Session-End review handler | 0=success, 1=issues, 2=error |
| `utils.py` | Shared utilities | N/A (module) |

---

## context_detector.py

**Purpose:** Detect code context and suggest appropriate review agents.

**Dependencies:** `git` (required), `gh` CLI (optional)

**Usage:**

```bash
python3 context_detector.py --suggest     # Context-aware suggestions
python3 context_detector.py --list        # List all agents
python3 context_detector.py --presets     # List available presets
python3 context_detector.py --context     # Show detected context
python3 context_detector.py --help        # Show help
```

**Output Examples:**

```bash
# --suggest
Quick review suggested (42 lines changed)
Agents: feature-dev:code-reviewer

# --list
Available agents:
  - feature-dev:code-reviewer
  - pr-review-toolkit:pr-test-analyzer
  - pr-review-toolkit:silent-failure-hunter
  ...

# --context
Repository: /path/to/repo
Branch: main
Changed files: 3
Lines changed: 127
File types: Python (2), Markdown (1)
```

**Functions:**

| Function | Description |
|----------|-------------|
| `detect_context()` | Detect repository context using git |
| `suggest_agents(context)` | Suggest agents based on context |
| `get_all_agents()` | Return list of all available agents |
| `get_presets()` | Return dict of preset configurations |
| `validate_environment()` | Check git/gh CLI availability |

**Constants:**

| Constant | Value | Purpose |
|----------|-------|---------|
| `CHANGE_SIZE_SMALL_THRESHOLD` | 50 | Lines for "quick" preset |
| `CHANGE_SIZE_LARGE_THRESHOLD` | 500 | Lines for "comprehensive" preset |
| `DEFAULT_GIT_TIMEOUT` | 5 | Git command timeout (seconds) |
| `DEFAULT_GH_TIMEOUT` | 5 | GitHub CLI timeout (seconds) |

---

## auto_review.py

**Purpose:** Handle Post-Write hook triggered reviews after file edits.

**Usage:**

```bash
python3 auto_review.py --file path/to/file.py          # Review single file
python3 auto_review.py --file path/to/file.py --strict  # Strict mode
python3 auto_review.py --help                          # Show help
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--file PATH` | Yes | Path to file to review |
| `--strict` | No | Enable strict mode (all checks) |

**Exit Codes:**

| Code | Meaning |
|------|---------|
| 0 | Success (no issues found) |
| 1 | Issues found (review completed with findings) |
| 2 | Error (script failed) |

**Output:**

Creates report in `~/.claude/plugins/multi-review/reports/review_YYYYMMDD-HHMMSS.json`

---

## pre_commit_check.py

**Purpose:** Handle Pre-Commit hook triggered reviews before git commits.

**Usage:**

```bash
python3 pre_commit_check.py              # Review staged files
python3 pre_commit_check.py --strict     # Strict mode (blocks commit on issues)
python3 pre_commit_check.py --help       # Show help
```

**Exit Codes:**

| Code | Meaning | Git Behavior |
|------|---------|--------------|
| 0 | Success | Commit proceeds |
| 1 | Issues found | Commit blocked (show findings) |
| 2 | Error | Commit blocked |

**Functions:**

| Function | Description |
|----------|-------------|
| `get_staged_files()` | Get list of staged files from git |
| `run_review(files)` | Run multi-agent review on files |
| `save_report(results)` | Save review report to disk |

**Output:**

Creates report in `~/.claude/plugins/multi-review/reports/commit_YYYYMMDD-HHMMSS.json`

---

## session_review.py

**Purpose:** Handle Session-End hook triggered reviews when Claude Code exits.

**Usage:**

```bash
python3 session_review.py                # Review session files
python3 session_review.py --full         # Comprehensive review
python3 session_review.py --help         # Show help
```

**Functions:**

| Function | Description |
|----------|-------------|
| `get_session_files(context_file)` | Get list of files modified during session |
| `detect_session_context()` | Detect overall session context |
| `run_session_review()` | Run review and save report |

**Output:**

Creates report in `~/.claude/plugins/multi-review/reports/session_YYYYMMDD-HHMMSS.json`

---

## utils.py

**Purpose:** Shared utilities for all scripts (imported as module).

**Functions:**

| Function | Description |
|----------|-------------|
| `setup_logging(level)` | Configure logging with specified level |
| `run_command(cmd, timeout)` | Run subprocess command with timeout |
| `parse_agent_list(agents_str)` | Parse agent list from string |
| `aggregate_results(results)` | Aggregate multi-agent results |

**Exit Code Constants:**

```python
EXIT_SUCCESS = 0           # Success, no issues
EXIT_ISSUES_FOUND = 1      # Issues found but review completed
EXIT_ERROR = 2             # Script error occurred
EXIT_TYPE_ERRORS = 3       # Reserved for LSP integration
```

**Usage Example:**

```python
from utils import setup_logging, run_command, EXIT_SUCCESS

logger = setup_logging(logging.INFO)
result = run_command(["git", "status"], timeout=5)
sys.exit(EXIT_SUCCESS)
```

---

## Logging

All scripts use Python stdlib `logging` module with consistent format:

```python
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
```

**Log Levels:**

- `INFO` - Normal operation messages
- `WARNING` - Non-critical issues
- `ERROR` - Errors that prevent operation
- `DEBUG` - Detailed debugging (use `--verbose` flag)

---

## Error Handling

All scripts follow consistent error handling pattern:

1. **Try-except wrapper** around main logic
2. **Actionable error messages** with suggestions
3. **Proper exit codes** for hook integration
4. **Graceful degradation** when optional tools missing

**Example:**

```python
try:
    context = detect_context()
    agents = suggest_agents(context)
except EnvironmentValidationError as e:
    logger.error(f"Environment error: {e}")
    sys.exit(EXIT_ERROR)
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    sys.exit(EXIT_ERROR)
```

---

## Testing

Run tests for individual scripts:

```bash
# Test context detector
pytest tests/test_context_detector.py

# Test auto review
pytest tests/test_auto_review.py

# Test utils
pytest tests/test_utils.py

# Run all tests
pytest
```

---

## Integration Points

### Hook Scripts

Bash wrapper scripts in `hooks/` directory call Python scripts:

```bash
#!/bin/bash
# hooks/post-write.sh
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "${PLUGIN_ROOT}/scripts/auto_review.py" "$@"
exit $?
```

### Plugin Commands

Commands in `commands/` directory invoke scripts:

```markdown
<!-- commands/multi-review.md -->
---
description: Multi-agent code review with smart agent selection
argument-hint: [--agents=quick|thorough|comprehensive|framework]
allowed-tools: ["Task", "Bash", "AskUserQuestion"]
---
```

---

## Development

**Add new script:**

1. Create file in `scripts/` directory
2. Add shebang: `#!/usr/bin/env python3`
3. Import `utils` for shared functions
4. Use stdlib only (no external dependencies)
5. Add tests to `tests/`
6. Update this reference

**Modify existing script:**

1. Maintain backward compatibility
2. Update tests to cover changes
3. Update docstrings and help text
4. Run full test suite before commit
