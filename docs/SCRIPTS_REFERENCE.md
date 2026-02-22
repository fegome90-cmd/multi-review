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
| `run_benchmark.py` | Benchmark execution harness | 0=success, 1=issues, 3=config_error |
| `bench_matcher.py` | Finding classification & matching | 0=success, 1=issues, 2=invalid_args |
| `check_gates.py` | Quality gate validation | 0=pass, 1=fail, 2=error |
| `feedback_manager.py` | Feedback collection & calibration | 0=success, 1=issues, 3=config_error |
| `feedback_manager_cli.py` | CLI for feedback management | 0=success, 1=issues, 2=invalid_args |
| `finding_filter.py` | Layer 2 finding filter | 0=success, 1=issues |
| `validation_pass.py` | Layer 3 validation | 0=success, 1=issues |
| `finding_aggregator.py` | Multi-agent result aggregation | 0=success, 1=issues |
| `xml_finding_parser.py` | XML finding parser | 0=success, 1=parse_error |
| `dspy_client.py` | DSPy integration client | 0=success, 1=error |
| `project_context.py` | Project context extraction | 0=success, 1=error |
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
# Canonical exit codes (use these)
from scripts.utils import ExitCodes

ExitCodes.SUCCESS = 0       # Normal successful execution
ExitCodes.FAILURE = 1       # General failure or issues found
ExitCodes.INVALID_ARGS = 2  # Invalid command-line arguments
ExitCodes.CONFIG_ERROR = 3  # Configuration or setup error
ExitCodes.ERROR = 4         # Runtime/operational error

# Legacy constants (deprecated, migrate carefully)
# Note: Semantics changed! Old EXIT_ERROR(2) != new ExitCodes.ERROR(4)
EXIT_SUCCESS = 0       # -> ExitCodes.SUCCESS
EXIT_ISSUES_FOUND = 1  # -> ExitCodes.FAILURE
EXIT_ERROR = 2         # -> ExitCodes.INVALID_ARGS (not ERROR!)
EXIT_TYPE_ERRORS = 3   # -> ExitCodes.CONFIG_ERROR
```

**Usage Example:**

```python
from utils import setup_logging, run_command, EXIT_SUCCESS

logger = setup_logging(logging.INFO)
result = run_command(["git", "status"], timeout=5)
sys.exit(EXIT_SUCCESS)
```

---

## run_benchmark.py

**Purpose:** Execute benchmark suites and measure review quality metrics.

**Dependencies:** `finding_filter.py`, `bench_matcher.py`, `feedback_manager.py`

**Usage:**

```bash
python3 run_benchmark.py                          # Run all benchmarks
python3 run_benchmark.py --fixture my_fixture     # Run specific fixture
python3 run_benchmark.py --preset quick           # Use quick preset
python3 run_benchmark.py --output results.json    # Save to file
python3 run_benchmark.py --help                   # Show help
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `--fixture NAME` | No | Run specific fixture only |
| `--preset NAME` | No | Use preset (quick, standard, thorough) |
| `--output PATH` | No | Write results to JSON file |
| `--warmup N` | No | Warmup runs before measurement (default: 2) |
| `--repeat N` | No | Repeat runs for averaging (default: 5) |

**Exit Codes:**

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `ExitCodes.SUCCESS` | Benchmark completed successfully |
| 1 | `ExitCodes.FAILURE` | Issues found in benchmark results |
| 2 | `ExitCodes.INVALID_ARGS` | Invalid command-line arguments |
| 3 | `ExitCodes.CONFIG_ERROR` | Configuration or fixture error |

**Classes:**

| Class | Description |
|-------|-------------|
| `BenchmarkConfig` | Configuration for benchmark execution |
| `BenchmarkResult` | Results including metrics and latencies |
| `FixtureData` | Test fixture with expected findings |

---

## bench_matcher.py

**Purpose:** Classify findings by matching against expected labels.

**Dependencies:** `finding_filter.py`, `utils.py`

**Usage:**

```bash
python3 bench_matcher.py --findings results.json --expected labels.json
python3 bench_matcher.py --help
```

**Classes:**

| Class | Description |
|-------|-------------|
| `Classification` | Enum: TP, FP, FN, SUPPRESSED |
| `MatchCriteria` | Criteria for matching findings |
| `ExpectedLabel` | Expected finding definition |
| `MatcherConfig` | Matcher configuration |
| `ClassificationResult` | Detailed classification result |

**Functions:**

| Function | Description |
|----------|-------------|
| `classify_finding()` | Classify single finding |
| `classify_finding_with_details()` | Classify with full details |
| `match_finding_to_label()` | Match finding to expected label |
| `calculate_metrics()` | Calculate precision/recall/F1 |

---

## check_gates.py

**Purpose:** Validate benchmark results against quality gates.

**Usage:**

```bash
python3 check_gates.py                      # Check all gates
python3 check_gates.py --results file.json  # Specific results file
python3 check_gates.py --json               # JSON output
python3 check_gates.py --help
```

**Exit Codes:**

| Code | Meaning |
|------|---------|
| 0 | All gates passed |
| 1 | One or more gates failed |
| 2 | Error loading results |

**Gate Checks:**

| Gate | Description |
|------|-------------|
| `check_fp_rate()` | False positive rate threshold |
| `check_latency()` | Latency threshold |
| `check_cache_hit_rate()` | Cache performance |
| `check_schema_stability()` | Output schema validation |

---

## feedback_manager.py

**Purpose:** Collect and manage feedback for agent calibration.

**Dependencies:** `finding_filter.py`, `utils.py`

**Usage:**

```bash
# Typically used as module, but can run standalone
python3 feedback_manager.py --status         # Show calibration status
python3 feedback_manager.py --export         # Export feedback data
python3 feedback_manager.py --help
```

**Classes:**

| Class | Description |
|-------|-------------|
| `FeedbackType` | Enum: FP, FN, SUPPRESSED |
| `FeedbackEntry` | Single feedback record |
| `AgentCalibration` | Agent calibration data |
| `FeedbackManager` | Main manager class |

**Key Methods:**

| Method | Description |
|--------|-------------|
| `record_feedback()` | Record new feedback |
| `get_calibration()` | Get agent calibration |
| `check_pattern_learning()` | Check learned patterns |
| `export_data()` | Export all feedback |

---

## feedback_manager_cli.py

**Purpose:** CLI interface for feedback management.

**Usage:**

```bash
python3 feedback_manager_cli.py status              # Show status
python3 feedback_manager_cli.py list                # List feedback
python3 feedback_manager_cli.py export --output fb.json
python3 feedback_manager_cli.py --help
```

---

## finding_filter.py

**Purpose:** Layer 2 finding filter with suppression rules.

**Dependencies:** `utils.py`

**Usage:**

```bash
python3 finding_filter.py --input findings.json --output filtered.json
python3 finding_filter.py --help
```

**Classes:**

| Class | Description |
|-------|-------------|
| `Finding` | Raw finding from agent |
| `FilteredFinding` | Finding with suppression info |
| `SuppressionRule` | Rule for suppressing findings |
| `FindingFilter` | Main filter class |

**Key Features:**

- Rule-based suppression
- Pattern learning from feedback
- Confidence thresholds
- Category filtering

---

## validation_pass.py

**Purpose:** Layer 3 validation for filtered findings.

**Dependencies:** `finding_filter.py`, `dspy_client.py`

**Usage:**

```bash
python3 validation_pass.py --input filtered.json --output validated.json
python3 validation_pass.py --help
```

**Functions:**

| Function | Description |
|----------|-------------|
| `validate_finding()` | Validate single finding |
| `run_validation_pass()` | Run full validation |
| `aggregate_validation_results()` | Aggregate results |

---

## finding_aggregator.py

**Purpose:** Aggregate results from multiple review agents.

**Usage:**

```bash
python3 finding_aggregator.py --results dir/ --output aggregated.json
python3 finding_aggregator.py --help
```

**Functions:**

| Function | Description |
|----------|-------------|
| `aggregate_results()` | Combine multiple results |
| `deduplicate_findings()` | Remove duplicate findings |
| `calculate_consensus()` | Find consensus across agents |

---

## xml_finding_parser.py

**Purpose:** Parse findings from XML agent output.

**Usage:**

```bash
python3 xml_finding_parser.py --input output.xml --output findings.json
python3 xml_finding_parser.py --help
```

**Security:**

- XXE protection via DTD/ENTITY detection
- Uses Python ElementTree (safe by default)

---

## dspy_client.py

**Purpose:** DSPy integration for ML-based validation.

**Usage:**

```bash
# Typically used as module
python3 dspy_client.py --test    # Test connection
python3 dspy_client.py --help
```

**Classes:**

| Class | Description |
|-------|-------------|
| `DSPyClient` | Client for DSPy API |
| `ValidationRequest` | Request payload |
| `ValidationResponse` | Response data |

---

## project_context.py

**Purpose:** Extract project context for review context.

**Usage:**

```bash
python3 project_context.py --output context.json
python3 project_context.py --help
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
