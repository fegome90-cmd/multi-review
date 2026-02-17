"""Tests for pre_commit_check.py module.

This test file follows TDD principles with comprehensive coverage
for the pre-commit hook functionality.
"""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

try:
    from pre_commit_check import (
        get_staged_files,
        run_pre_commit_review,
        filter_reviewable_files,
        save_commit_report,
        main
    )
    # Alias for compatibility with test naming
    run_review = run_pre_commit_review
    save_report = save_commit_report
except ImportError as e:
    pytest.skip(f"Cannot import pre_commit_check: {e}", allow_module_level=True)


class TestGetStagedFiles:
    """Tests for get_staged_files function."""

    @patch('subprocess.run')
    def test_returns_list_of_path_objects(self, mock_run):
        """Should return list of Path objects from git output."""
        mock_run.return_value = Mock(
            stdout="src/main.py\ntests/test_main.py\nscripts/helper.py\n",
            returncode=0
        )

        files = get_staged_files()

        assert isinstance(files, list)
        assert len(files) == 3
        assert all(isinstance(f, Path) for f in files)
        assert files[0] == Path("src/main.py")
        assert files[1] == Path("tests/test_main.py")
        assert files[2] == Path("scripts/helper.py")

    @patch('subprocess.run')
    def test_returns_empty_list_when_no_files(self, mock_run):
        """Should return empty list when git returns no output."""
        mock_run.return_value = Mock(stdout="", returncode=0)

        files = get_staged_files()

        assert files == []

    @patch('subprocess.run')
    def test_handles_git_command_timeout_gracefully(self, mock_run):
        """Should return empty list on timeout instead of raising."""
        mock_run.side_effect = subprocess.TimeoutExpired("git", 10)

        files = get_staged_files()

        # Should handle gracefully and return empty list
        assert files == []

    @patch('subprocess.run')
    def test_handles_subprocess_error(self, mock_run):
        """Should return empty list on subprocess error."""
        mock_run.side_effect = OSError("Git not found")

        files = get_staged_files()

        # Should handle gracefully and return empty list
        assert files == []

    @patch('subprocess.run')
    def test_returns_all_files_from_git(self, mock_run):
        """Should return all files from git output."""
        mock_run.return_value = Mock(
            stdout="src/main.py\nREADME.md\ndata.csv\n",
            returncode=0
        )

        files = get_staged_files()

        # Returns all files from git (filtering happens elsewhere)
        assert len(files) == 3

    @patch('subprocess.run')
    def test_handles_nonzero_git_exit(self, mock_run):
        """Should return empty list when git returns non-zero exit."""
        mock_run.return_value = Mock(
            stdout="",
            returncode=1
        )

        files = get_staged_files()

        assert files == []


class TestRunReview:
    """Tests for run_review function."""

    def test_returns_success_dict_for_empty_files(self):
        """Should return success dict when files list is empty."""
        result = run_review([])

        assert result["success"] is True
        assert result["files_reviewed"] == 0
        assert result["issues_found"] == 0
        assert result["critical_count"] == 0

    @patch('subprocess.run')
    def test_suggests_quick_preset_for_single_file(self, mock_run):
        """Should suggest quick preset for single file review."""
        mock_run.return_value = Mock(
            stdout='{"available_agents": ["code-reviewer"]}',
            returncode=0
        )

        result = run_review([Path("test.py")])

        assert result["success"] is True
        assert result["preset"] == "quick"
        assert result["files_reviewed"] == 1

    @patch('subprocess.run')
    def test_suggests_thorough_preset_for_few_files(self, mock_run):
        """Should suggest thorough preset for 2-5 files."""
        mock_run.return_value = Mock(
            stdout='{"available_agents": ["code-reviewer"]}',
            returncode=0
        )

        files = [Path(f"test{i}.py") for i in range(3)]
        result = run_review(files)

        assert result["success"] is True
        assert result["preset"] == "thorough"
        assert result["files_reviewed"] == 3

    @patch('subprocess.run')
    def test_suggests_comprehensive_preset_for_many_files(self, mock_run):
        """Should suggest comprehensive preset for 6+ files."""
        mock_run.return_value = Mock(
            stdout='{"available_agents": ["code-reviewer"]}',
            returncode=0
        )

        files = [Path(f"test{i}.py") for i in range(10)]
        result = run_review(files)

        assert result["success"] is True
        assert result["preset"] == "comprehensive"
        assert result["files_reviewed"] == 10

    @patch('subprocess.run')
    def test_handles_context_detector_failure(self, mock_run):
        """Should handle context detector script failure gracefully."""
        mock_run.side_effect = OSError("Script not found")

        result = run_review([Path("test.py")])

        assert result["success"] is False
        assert "error" in result

    @patch('subprocess.run')
    def test_returns_dict_result(self, mock_run):
        """Should return dict not string."""
        mock_run.return_value = Mock(
            stdout='{"available_agents": ["code-reviewer"]}',
            returncode=0
        )

        result = run_review([Path("test.py")])

        assert isinstance(result, dict)
        assert "preset" in result
        assert "files_reviewed" in result


class TestFilterReviewableFiles:
    """Tests for filter_reviewable_files function."""

    def test_filters_python_files(self):
        """Should include Python files."""
        files = [Path("test.py"), Path("README.md"), Path("data.json")]
        filtered = filter_reviewable_files(files)

        assert len(filtered) == 1
        assert filtered[0].suffix == ".py"

    def test_filters_reviewable_extensions(self):
        """Should include all code file extensions."""
        files = [
            Path("test.py"),
            Path("app.ts"),
            Path("lib.js"),
            Path("main.go"),
            Path("data.csv"),  # Not reviewable
            Path("README.md"),  # Not reviewable
        ]
        filtered = filter_reviewable_files(files)

        assert len(filtered) == 4

    def test_excludes_common_directories(self):
        """Should exclude files in common build/cache directories."""
        files = [
            Path("src/main.py"),
            Path("node_modules/pkg/index.js"),
            Path("venv/lib/module.py"),
            Path(".venv/lib/module.py"),
            Path("dist/bundle.js"),
        ]
        filtered = filter_reviewable_files(files)

        assert len(filtered) == 1
        assert filtered[0] == Path("src/main.py")

    def test_handles_nested_paths(self):
        """Should handle nested directory paths."""
        files = [
            Path("src/components/Button.tsx"),
            Path("node_modules/@types/react/index.d.ts"),
        ]
        filtered = filter_reviewable_files(files)

        assert len(filtered) == 1
        assert "components" in str(filtered[0])


class TestSaveReport:
    """Tests for save_commit_report function."""

    @patch('pre_commit_check.save_report')
    def test_calls_utils_save_report_with_correct_params(self, mock_utils_save):
        """Should call utils.save_report with report_type='commit'."""
        results = {"findings": []}
        files = []
        mock_utils_save.return_value = Path("report.json")

        save_commit_report(results, files)

        # Verify save_report was called with correct params
        mock_utils_save.assert_called_once()
        call_args = mock_utils_save.call_args
        assert call_args[0][1] == "commit"  # report_type parameter

    @patch('pre_commit_check.save_report')
    def test_includes_files_in_report_data(self, mock_utils_save):
        """Should include file list in report data."""
        results = {"findings": []}
        files = [Path("test.py"), Path("main.py")]
        mock_utils_save.return_value = Path("report.json")

        save_commit_report(results, files)

        # Verify the report data includes files
        call_args = mock_utils_save.call_args
        report_data = call_args[0][0]  # First positional arg
        assert "files" in report_data
        assert report_data["files"] == ["test.py", "main.py"]
        assert "results" in report_data
        assert report_data["results"] == results

    @patch('pre_commit_check.save_report')
    def test_returns_path_from_utils_save_report(self, mock_utils_save):
        """Should return the path from utils.save_report."""
        results = {"findings": []}
        files = []
        expected_path = Path("reports/commit_20250209-120000.json")
        mock_utils_save.return_value = expected_path

        result = save_commit_report(results, files)

        assert result == expected_path


class TestMain:
    """Tests for main function."""

    @patch('pre_commit_check.sys.argv', ['pre_commit_check.py'])
    @patch('pre_commit_check.get_staged_files')
    @patch('pre_commit_check.filter_reviewable_files')
    @patch('pre_commit_check.run_pre_commit_review')
    @patch('pre_commit_check.save_commit_report')
    def test_returns_zero_on_success(self, mock_save, mock_run, mock_filter, mock_files):
        """Should return 0 when review succeeds."""
        mock_files.return_value = [Path("test.py")]
        mock_filter.return_value = [Path("test.py")]
        mock_run.return_value = {
            "success": True,
            "preset": "quick",
            "files_reviewed": 1,
            "critical_count": 0
        }

        exit_code = main()

        assert exit_code == 0

    @patch('pre_commit_check.sys.argv', ['pre_commit_check.py', '--strict'])
    @patch('pre_commit_check.get_staged_files')
    @patch('pre_commit_check.filter_reviewable_files')
    @patch('pre_commit_check.run_pre_commit_review')
    @patch('pre_commit_check.save_commit_report')
    def test_returns_one_on_critical_in_strict_mode(self, mock_save, mock_run, mock_filter, mock_files):
        """Should return 1 when critical issues in strict mode."""
        mock_files.return_value = [Path("test.py")]
        mock_filter.return_value = [Path("test.py")]
        mock_run.return_value = {
            "success": True,
            "preset": "quick",
            "files_reviewed": 1,
            "critical_count": 2
        }

        exit_code = main()

        assert exit_code == 1

    @patch('pre_commit_check.sys.argv', ['pre_commit_check.py'])
    @patch('pre_commit_check.get_staged_files')
    def test_returns_zero_when_no_staged_files(self, mock_files):
        """Should return 0 when no files staged."""
        mock_files.return_value = []

        exit_code = main()

        assert exit_code == 0

    @patch('pre_commit_check.sys.argv', ['pre_commit_check.py'])
    @patch('pre_commit_check.get_staged_files')
    @patch('pre_commit_check.filter_reviewable_files')
    @patch('pre_commit_check.run_pre_commit_review')
    @patch('pre_commit_check.save_commit_report')
    def test_saves_report_before_exit(self, mock_save, mock_run, mock_filter, mock_files):
        """Should save report to disk before exiting."""
        mock_files.return_value = [Path("test.py")]
        mock_filter.return_value = [Path("test.py")]
        mock_run.return_value = {
            "success": True,
            "preset": "quick",
            "files_reviewed": 1,
            "critical_count": 0
        }

        main()

        mock_save.assert_called_once()

    @patch('pre_commit_check.sys.argv', ['pre_commit_check.py'])
    @patch('pre_commit_check.get_staged_files')
    @patch('pre_commit_check.filter_reviewable_files')
    @patch('pre_commit_check.run_pre_commit_review')
    @patch('pre_commit_check.save_commit_report')
    def test_returns_three_on_review_failure(self, mock_save, mock_run, mock_filter, mock_files):
        """Should return 3 (CONFIG_ERROR) when review fails."""
        mock_files.return_value = [Path("test.py")]
        mock_filter.return_value = [Path("test.py")]
        mock_run.return_value = {
            "success": False,
            "error": "Context detection failed"
        }

        exit_code = main()

        # ExitCodes.CONFIG_ERROR is 3
        assert exit_code == 3
