# Multi-Review Plugin Quality Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 3 critical and 8 important code quality issues detected in multi-review plugin E2E test

**Architecture:** Centralize exit codes in utils.py, consolidate duplicate report saving, fix metrics bug, improve error handling. All changes follow DRY principle and preserve existing functionality.

**Tech Stack:** Python 3.11+, uv, pytest, mypy strict, ruff

---

## Pre-Flight Checks

### Task 0: Setup and Verification

**Files:**
- Read: `~/.claude/plugins/multi-review/pyproject.toml`
- Run: `cd ~/.claude/plugins/multi-review && uv run pytest tests/ -v`

**Step 1: Verify test suite runs**

```bash
cd ~/.claude/plugins/multi-review
uv run pytest tests/ -v
```

Expected: All existing tests pass (baseline)

**Step 2: Create feature branch**

```bash
cd ~/.claude/plugins/multi-review
git checkout -b feature/quality-fixes
```

Expected: Clean checkout to new branch

---

## Phase 1: Critical Fixes (Exit Codes Standardization)

### Task 1: Centralize Exit Codes in utils.py

**Files:**
- Modify: `scripts/utils.py:25-29`

**Step 1: Write the failing test**

```python
# tests/test_utils_exit_codes.py
def test_exit_codes_are_consistent():
    """Exit codes should use consistent naming across all modules."""
    from scripts import utils
    from scripts import pre_commit_check
    from scripts import session_review
    from scripts import auto_review

    # All modules should import from utils, not define their own
    assert hasattr(utils, 'EXIT_SUCCESS')
    assert hasattr(utils, 'EXIT_ISSUES')
    assert hasattr(utils, 'EXIT_ERROR')

    # These should NOT exist after fix
    assert not hasattr(pre_commit_check, 'EXIT_FAIL')
    assert not hasattr(session_review, 'EXIT_ISSUES')  # if different from utils
    assert not hasattr(pre_commit_check, 'EXIT_PASS')
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_utils_exit_codes.py::test_exit_codes_are_consistent -v
```

Expected: FAIL (modules currently define their own constants)

**Step 3: Update utils.py with canonical exit codes**

```python
# scripts/utils.py - Replace lines 25-29 with:
# Exit codes - single source of truth
EXIT_SUCCESS = 0
EXIT_ISSUES = 1      # Issues found during review/scan
EXIT_ERROR = 2       # Execution error (exception, invalid input, etc.)
EXIT_TYPE_ERRORS = 3 # Type checking errors (optional, for type-check mode)
```

**Step 4: Update pre_commit_check.py to use utils constants**

```python
# scripts/pre_commit_check.py - Replace lines 37-40:
from scripts.utils import EXIT_SUCCESS as PASS, EXIT_ISSUES as FAIL, EXIT_ERROR

# Update line 218: return EXIT_SUCCESS → return PASS
# Update line 221: return EXIT_ISSUES_FOUND → return FAIL
# Update line 224: return EXIT_ERROR → return EXIT_ERROR
```

**Step 5: Update session_review.py to use utils constants**

```python
# scripts/session_review.py - Replace lines 36-39:
from scripts.utils import EXIT_SUCCESS, EXIT_ISSUES, EXIT_ERROR

# Update all references:
# EXIT_SUCCESS → remains EXIT_SUCCESS (from utils)
# EXIT_ISSUES → replaces EXIT_ISSUES
# EXIT_ERROR → remains EXIT_ERROR (from utils)
```

**Step 6: Update auto_review.py if it has exit codes**

```bash
grep -n "EXIT_" scripts/auto_review.py
```

If found, import from utils.py instead of defining locally.

**Step 7: Run test to verify it passes**

```bash
uv run pytest tests/test_utils_exit_codes.py::test_exit_codes_are_consistent -v
```

Expected: PASS

**Step 8: Run full test suite to ensure no regressions**

```bash
uv run pytest tests/ -v
```

Expected: All tests pass

**Step 9: Commit**

```bash
git add scripts/utils.py scripts/pre_commit_check.py scripts/session_review.py tests/test_utils_exit_codes.py
git commit -m "fix: standardize exit code constants across all scripts

- Move canonical exit codes to utils.py (EXIT_SUCCESS, EXIT_ISSUES, EXIT_ERROR)
- Remove duplicate definitions from pre_commit_check.py and session_review.py
- Add test to prevent re-introduction of inconsistent naming

Fixes #1 from TEST_REPORT_2025-02-09"
```

---

## Phase 2: Critical Fixes (Consolidate save_report)

### Task 2: Consolidate Report Saving in utils.py

**Files:**
- Modify: `scripts/utils.py:52-90`
- Modify: `scripts/pre_commit_check.py:186-213`
- Modify: `scripts/session_review.py:140-168`
- Create: `tests/test_utils_save_report.py`

**Step 1: Write the failing test**

```python
# tests/test_utils_save_report.py
def test_save_report_handles_commit_and_session_types():
    """save_report should handle different report types via parameter."""
    from scripts.utils import save_report
    from pathlib import Path
    import tempfile
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        # Monkey patch get_reports_dir
        import scripts.utils as utils_module
        original = utils_module.get_reports_dir
        utils_module.get_reports_dir = lambda: Path(tmpdir)

        try:
            # Test commit report
            commit_report = save_report(
                {"files": ["test.py"], "results": {}},
                report_type="commit"
            )
            assert commit_report is not None
            data = json.loads(commit_report.read_text())
            assert data["report_type"] == "commit"

            # Test session report
            session_report = save_report(
                {"files": ["test.py"], "results": {}},
                report_type="session"
            )
            assert session_report is not None
            data = json.loads(session_report.read_text())
            assert data["report_type"] == "session"
        finally:
            utils_module.get_reports_dir = original
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_utils_save_report.py::test_save_report_handles_commit_and_session_types -v
```

Expected: FAIL (save_report doesn't accept report_type parameter)

**Step 3: Enhance utils.save_report() to support report_type**

```python
# scripts/utils.py - Modify save_report function (lines 52-90):

def save_report(
    report_data: dict[str, Any],
    report_type: str = "general"
) -> Path | None:
    """
    Save report data to a timestamped file in the reports directory.

    Args:
        report_data: Dictionary containing report data
        report_type: Type of report (commit, session, general, etc.)

    Returns:
        Path to saved report file, or None if save failed
    """
    reports_dir = get_reports_dir()

    # Add metadata
    report_data["timestamp"] = generate_timestamp()
    report_data["report_type"] = report_type

    filename = f"{report_type}_{generate_timestamp()}.json"
    filepath = reports_dir / filename

    try:
        filepath.write_text(json.dumps(report_data, indent=2))
        return filepath
    except (OSError, PermissionError) as e:
        print(f"ERROR: Cannot save report: {e}", file=sys.stderr)
        return None
```

**Step 4: Update pre_commit_check.py to use consolidated save_report**

```python
# scripts/pre_commit_check.py - Replace save_commit_report (lines 186-213):

from scripts.utils import save_report

# In run_check() function, replace the save_commit_report call:
# Old: result = save_commit_report(results, files)
# New:
result = save_report(
    {
        "files": [str(f) for f in files],
        "results": results,
    },
    report_type="commit"
)

# Delete the save_commit_report function entirely (lines 186-213)
```

**Step 5: Update session_review.py to use consolidated save_report**

```python
# scripts/session_review.py - Replace save_session_report (lines 140-168):

from scripts.utils import save_report

# In save_end_report() function, replace the save_session_report call:
# Old: result = save_session_report(results, files)
# New:
result = save_report(
    {
        "files": [str(f) for f in files],
        "results": results,
        "session_type": "end",
    },
    report_type="session"
)

# Delete the save_session_report function entirely (lines 140-168)
```

**Step 6: Run test to verify it passes**

```bash
uv run pytest tests/test_utils_save_report.py -v
```

Expected: PASS

**Step 7: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All tests pass

**Step 8: Commit**

```bash
git add scripts/utils.py scripts/pre_commit_check.py scripts/session_review.py tests/test_utils_save_report.py
git commit -m "refactor: consolidate duplicate report saving logic

- Enhance utils.save_report() to accept report_type parameter
- Remove duplicate save_commit_report() from pre_commit_check.py
- Remove duplicate save_session_report() from session_review.py
- Add test for report_type parameter

Reduces code duplication by ~80 lines.
Fixes #2 from TEST_REPORT_2025-02-09"
```

---

## Phase 3: Critical Fixes (Metrics Recording Bug)

### Task 3: Fix Metrics Recording Bug in validate_sarif.py

**Files:**
- Modify: `plugins/production_ready/scripts/validate_sarif.py:224-228`

**Step 1: Locate the bug**

```bash
grep -n "return True" plugins/production_ready/scripts/validate_sarif.py | head -5
```

Expected: Find line 228 with early return

**Step 2: Write the failing test**

```python
# plugins/production_ready/tests/test_validate_sarif_metrics.py
def test_metrics_recorded_on_validation_success():
    """Metrics should be recorded even when validation succeeds."""
    from unittest.mock import Mock, patch
    from scripts.validate_sarif import validate_runs_array

    mock_metrics = Mock()
    mock_finder = Mock()
    mock_finder.find_errors.return_value = []  # No errors = valid

    # Mock duration timing
    with patch('time.time', return_value=100.0):
        result = validate_runs_array(
            sarif_data={"runs": []},
            args=Mock(),
            metrics=mock_metrics,
            finder=mock_finder
        )

    assert result is True
    # Verify metrics were recorded
    mock_metrics.record_duration.assert_called_once()
```

**Step 3: Run test to verify it fails**

```bash
cd plugins/production_ready
uv run pytest tests/test_validate_sarif_metrics.py::test_metrics_recorded_on_validation_success -v
```

Expected: FAIL (metrics.record_duration not called due to early return)

**Step 4: Fix the bug - move metrics recording before return**

```python
# plugins/production_ready/scripts/validate_sarif.py - Lines 224-228:

# OLD CODE:
    if len(errors) == 0:
        return True  # ← BUG: metrics recording below never executes

    # This code never runs:
    self.metrics.record_duration(...)

# NEW CODE:
    # Record metrics BEFORE returning
    duration = time.time() - start_time
    self.metrics.record_duration("validate_sarif", duration, {"runs_count": len(runs)})

    if len(errors) == 0:
        return True
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/test_validate_sarif_metrics.py::test_metrics_recorded_on_validation_success -v
```

Expected: PASS

**Step 6: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All tests pass

**Step 7: Commit**

```bash
cd plugins/production_ready
git add scripts/validate_sarif.py tests/test_validate_sarif_metrics.py
git commit -m "fix: record metrics even when validation succeeds

- Move metrics.record_duration() before early return
- Add test to verify metrics are always recorded

Fixes #3 from TEST_REPORT_2025-02-09"
```

---

## Phase 4: Important Fixes (Error Handling & Validation)

### Task 4: Add Preset Validation in auto_review.py

**Files:**
- Modify: `scripts/auto_review.py:126-137`
- Create: `tests/test_auto_review_preset_validation.py`

**Step 1: Write the failing test**

```python
# tests/test_auto_review_preset_validation.py
import pytest

def test_invalid_preset_raises_error():
    """Invalid preset should raise ValueError with helpful message."""
    from scripts.auto_review import main
    from scripts.context_detector import AGENT_PRESETS

    # Mock sys.argv
    import sys
    original_argv = sys.argv

    try:
        sys.argv = ["auto_review.py", "--preset", "nonexistent_preset"]

        with pytest.raises(ValueError, match="Invalid preset"):
            main()
    finally:
        sys.argv = original_argv

def test_valid_preset_accepted():
    """Valid presets from AGENT_PRESETS should be accepted."""
    from scripts.context_detector import AGENT_PRESETS

    for preset_name in AGENT_PRESETS.keys():
        # Verify preset exists in mapping
        assert preset_name in AGENT_PRESETS
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_auto_review_preset_validation.py -v
```

Expected: FAIL (no validation currently)

**Step 3: Add preset validation**

```python
# scripts/auto_review.py - Add after line 120:

from scripts.context_detector import AGENT_PRESETS

def _validate_preset(preset_name: str) -> str:
    """
    Validate preset exists and return canonical name.

    Args:
        preset_name: User-provided preset name

    Returns:
        Canonical preset name

    Raises:
        ValueError: If preset doesn't exist
    """
    if preset_name not in AGENT_PRESETS:
        available = ", ".join(sorted(Agent_PRESETS.keys()))
        raise ValueError(
            f"Invalid preset '{preset_name}'. Available presets: {available}"
        )
    return preset_name

# In main(), add validation after argparse:
if args.preset:
    args.preset = _validate_preset(args.preset)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_auto_review_preset_validation.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add scripts/auto_review.py tests/test_auto_review_preset_validation.py
git commit -m "feat: add preset validation with helpful error message

- Validate preset exists before using it
- Show available presets in error message
- Add tests for validation

Fixes #5 from TEST_REPORT_2025-02-09"
```

---

### Task 5: Remove Redundant try/except in context_detector.py

**Files:**
- Modify: `scripts/context_detector.py:167-170`
- Create: `tests/test_context_detector_error_handling.py`

**Step 1: Write test to verify RuntimeError propagates**

```python
# tests/test_context_detector_error_handling.py
import pytest

def test_runtime_error_propagates_from_run_git_command():
    """RuntimeError from git operations should propagate to caller."""
    from scripts.context_detector import _run_git_command
    from unittest.mock import patch, Mock

    mock_process = Mock()
    mock_process.stderr = b"fatal: index.lock exists"
    mock_process.returncode = 1

    with patch('subprocess.run', return_value=mock_process):
        with pytest.raises(RuntimeError, match="Git operation failed"):
            _run_git_command(["git", "status"], "test operation")
```

**Step 2: Remove redundant exception handler**

```python
# scripts/context_detector.py - Lines 167-170:

# OLD CODE:
    try:
        # ... git command ...
    except subprocess.CalledProcessError as e:
        # ... error handling ...
    except RuntimeError:
        # Re-raise RuntimeError already raised above
        raise  # ← REDUNDANT

# NEW CODE (just remove lines 167-170 entirely):
    try:
        # ... git command ...
    except subprocess.CalledProcessError as e:
        # ... error handling ...
    # RuntimeError propagates naturally
```

**Step 3: Run test**

```bash
uv run pytest tests/test_context_detector_error_handling.py -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add scripts/context_detector.py tests/test_context_detector_error_handling.py
git commit -m "refactor: remove redundant exception handler

- Remove unnecessary 'except RuntimeError: raise' pattern
- RuntimeError now propagates naturally
- Add test to verify error propagation

Fixes #6 from TEST_REPORT_2025-02-09"
```

---

### Task 6: Fix Type Hints in gate_evaluator.py

**Files:**
- Modify: `plugins/production_ready/scripts/gate_evaluator.py:365-390`

**Step 1: Check current type hints**

```bash
grep -A 5 "def load_agent_runs" plugins/production_ready/scripts/gate_evaluator.py
```

**Step 2: Write test for type compliance**

```python
# plugins/production_ready/tests/test_gate_evaluator_types.py
def test_load_agent_runs_return_type():
    """Function should return correct tuple type."""
    from scripts.gate_evaluator import load_agent_runs
    from pathlib import Path

    result, errors = load_agent_runs(Path("test_data/agent_runs.jsonl"))

    # Type assertions
    assert isinstance(result, list)
    assert isinstance(errors, int)
```

**Step 3: Ensure all return paths have correct type**

```python
# plugins/production_ready/scripts/gate_evaluator.py - Ensure function signature:

def load_agent_runs(
    filepath: Path,
) -> tuple[list[dict[str, Any]], int]:
    """
    Load and parse agent runs from JSONL file.

    Returns:
        Tuple of (runs_list, error_count)
    """
    runs: list[dict[str, Any]] = []
    errors: int = 0

    # ... parsing logic ...

    # Ensure all return paths return (runs, errors)
    return runs, errors
```

**Step 4: Run mypy to verify**

```bash
cd plugins/production_ready
uv run mypy scripts/gate_evaluator.py --strict
```

Expected: No type errors

**Step 5: Commit**

```bash
git add scripts/gate_evaluator.py tests/test_gate_evaluator_types.py
git commit -m "fix: ensure consistent return types in load_agent_runs

- All return paths now return (runs, errors) tuple
- Add type hints for all variables
- Passes mypy strict type checking

Fixes #10 from TEST_REPORT_2025-02-09"
```

---

## Phase 5: Cleanup and Documentation

### Task 7: Update CLAUDE.md with Fixes

**Files:**
- Modify: `CLAUDE.md` (if exists in multi-review)

**Step 1: Document exit codes location**

```markdown
## Exit Codes

All exit codes are defined in `scripts/utils.py`:
- `EXIT_SUCCESS = 0` - No issues found
- `EXIT_ISSUES = 1` - Issues found during review
- `EXIT_ERROR = 2` - Execution error

Import from utils.py, do not redefine locally.
```

**Step 2: Document report saving**

```markdown
## Report Saving

Use `save_report()` from `scripts/utils.py` for all report types:

```python
from scripts.utils import save_report

save_report(
    {"data": "value"},
    report_type="commit"  # or "session", "general"
)
```

Do not create duplicate save_*_report functions.
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document exit codes and report saving patterns"
```

---

### Task 8: Final Verification and PR

**Step 1: Run full test suite**

```bash
cd ~/.claude/plugins/multi-review
uv run pytest tests/ -v --cov=scripts --cov-report=term-missing
```

Expected: All tests pass, coverage >80%

**Step 2: Run type checking**

```bash
uv run mypy scripts/ --strict
```

Expected: No type errors

**Step 3: Run linting**

```bash
uv run ruff check scripts/ tests/
```

Expected: No lint errors

**Step 4: Format code**

```bash
uv run ruff format scripts/ tests/
```

**Step 5: Push to remote**

```bash
git push -u origin feature/quality-fixes
```

**Step 6: Create PR (if applicable)**

```bash
gh pr create --title "Fix critical and important code quality issues" --body "
## Summary
- Standardize exit codes across all scripts (#1)
- Consolidate duplicate report saving logic (#2)
- Fix metrics recording bug (#3)
- Add preset validation (#5)
- Remove redundant exception handler (#6)
- Fix type hints (#10)

## Test Plan
- [x] All existing tests pass
- [x] New tests added for all fixes
- [x] mypy strict passes
- [x] ruff linting passes
- [x] Coverage maintained

Fixes issues from TEST_REPORT_2025-02-09
"
```

---

## Summary

This plan fixes **11 issues** (3 critical, 8 important) from the E2E test report:

| Phase | Task | Issue | Lines Changed |
|-------|------|-------|---------------|
| 1 | Exit codes | #1 Critical | ~30 |
| 2 | Report saving | #2 Critical | ~100 (net -80) |
| 3 | Metrics bug | #3 Critical | ~5 |
| 4 | Preset validation | #5 Important | ~20 |
| 5 | Redundant except | #6 Important | ~5 |
| 6 | Type hints | #10 Important | ~10 |

**Estimated effort:** 2-3 hours following TDD methodology

**Risk:** Low - all changes are consolidations or bug fixes with test coverage
