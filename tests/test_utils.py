"""Tests for utils.py module."""

import json
import pytest
from pathlib import Path

from utils import (
    ExitCodes,
    EXIT_SUCCESS,
    EXIT_ISSUES_FOUND,
    EXIT_ERROR,
    EXIT_TYPE_ERRORS,
    get_reports_dir,
    generate_timestamp,
    save_report,
    format_report_summary,
    log_review_summary,
    validate_file_path,
    count_lines_safely,
)


class TestExitCodes:
    """Tests for exit code constants."""

    def test_exit_codes_class_exists(self):
        """ExitCodes class should be defined."""
        assert hasattr(ExitCodes, 'SUCCESS')
        assert hasattr(ExitCodes, 'FAILURE')
        assert hasattr(ExitCodes, 'INVALID_ARGS')
        assert hasattr(ExitCodes, 'CONFIG_ERROR')

    def test_exit_codes_class_are_integers(self):
        """ExitCodes class attributes should be integers."""
        assert isinstance(ExitCodes.SUCCESS, int)
        assert isinstance(ExitCodes.FAILURE, int)
        assert isinstance(ExitCodes.INVALID_ARGS, int)
        assert isinstance(ExitCodes.CONFIG_ERROR, int)

    def test_exit_codes_class_have_expected_values(self):
        """ExitCodes class should have standard values."""
        assert ExitCodes.SUCCESS == 0
        assert ExitCodes.FAILURE == 1
        assert ExitCodes.INVALID_ARGS == 2
        assert ExitCodes.CONFIG_ERROR == 3

    def test_legacy_exit_codes_are_integers(self):
        """Legacy exit codes should be integers."""
        assert isinstance(EXIT_SUCCESS, int)
        assert isinstance(EXIT_ISSUES_FOUND, int)
        assert isinstance(EXIT_ERROR, int)
        assert isinstance(EXIT_TYPE_ERRORS, int)

    def test_legacy_exit_codes_have_expected_values(self):
        """Legacy exit codes should have standard values."""
        assert EXIT_SUCCESS == 0
        assert EXIT_ISSUES_FOUND == 1
        assert EXIT_ERROR == 2
        assert EXIT_TYPE_ERRORS == 3

    def test_exit_codes_match_legacy_codes(self):
        """New ExitCodes should match legacy codes for consistency."""
        assert ExitCodes.SUCCESS == EXIT_SUCCESS
        assert ExitCodes.FAILURE == EXIT_ISSUES_FOUND


class TestReportsDirectory:
    """Tests for reports directory handling."""

    def test_get_reports_dir_returns_path(self):
        """get_reports_dir should return a Path object."""
        reports_dir = get_reports_dir()
        assert isinstance(reports_dir, Path)

    def test_get_reports_dir_exists(self):
        """get_reports_dir should create the directory if needed."""
        reports_dir = get_reports_dir()
        assert reports_dir.exists()
        assert reports_dir.is_dir()


class TestTimestampGeneration:
    """Tests for timestamp generation."""

    def test_generate_timestamp_returns_string(self):
        """generate_timestamp should return a string."""
        timestamp = generate_timestamp()
        assert isinstance(timestamp, str)

    def test_generate_timestamp_format(self):
        """Timestamp should follow YYYYMMDD-HHMMSS format."""
        timestamp = generate_timestamp()
        assert len(timestamp) == 15  # YYYYMMDD-HHMMSS
        assert timestamp[8] == "-"


class TestSaveReport:
    """Tests for report saving."""

    def test_save_report_creates_file(self, tmp_path):
        """save_report should create a report file."""
        # Use tmp_path for isolated testing
        import utils
        original_get_reports_dir = utils.get_reports_dir
        utils.get_reports_dir = lambda: tmp_path

        try:
            report_data = {"test": "data"}
            result = save_report(report_data, "test")
            assert result is not None
            assert result.exists()
            assert result.is_file()
        finally:
            utils.get_reports_dir = original_get_reports_dir

    def test_save_report_includes_timestamp(self, tmp_path):
        """Saved report should include timestamp."""
        import utils
        original_get_reports_dir = utils.get_reports_dir
        utils.get_reports_dir = lambda: tmp_path

        try:
            report_data = {"test": "data"}
            result = save_report(report_data, "test")
            saved_content = json.loads(result.read_text())
            assert "timestamp" in saved_content
        finally:
            utils.get_reports_dir = original_get_reports_dir

    def test_save_report_handles_os_error(self, tmp_path):
        """save_report should handle OS errors gracefully."""
        import utils
        original_get_reports_dir = utils.get_reports_dir

        # Make directory read-only to cause error
        tmp_path.chmod(0o444)
        utils.get_reports_dir = lambda: tmp_path

        try:
            report_data = {"test": "data"}
            result = save_report(report_data, "test")
            # Should return None on error
            assert result is None
        finally:
            # Restore permissions for cleanup
            tmp_path.chmod(0o755)
            utils.get_reports_dir = original_get_reports_dir


class TestFormatReportSummary:
    """Tests for report summary formatting."""

    def test_format_report_summary_returns_dict(self):
        """format_report_summary should return a dictionary."""
        summary = format_report_summary("quick", ["agent1", "agent2"])
        assert isinstance(summary, dict)

    def test_format_report_summary_contains_keys(self):
        """Summary should contain all expected keys."""
        summary = format_report_summary(
            "quick",
            ["agent1", "agent2"],
            issues_found=5,
            critical_count=1
        )
        assert summary["preset"] == "quick"
        assert summary["agents"] == ["agent1", "agent2"]
        assert summary["issues_found"] == 5
        assert summary["critical_count"] == 1


class TestValidateFilePath:
    """Tests for file path validation."""

    def test_validate_none_path(self):
        """None path should return False."""
        assert validate_file_path(None) is False

    def test_validate_nonexistent_path(self, tmp_path):
        """Nonexistent path should return False."""
        assert validate_file_path(tmp_path / "nonexistent.txt") is False

    def test_validate_existing_file(self, temp_file):
        """Existing file should return True."""
        assert validate_file_path(temp_file) is True

    def test_validate_directory_returns_false(self, tmp_path):
        """Directory path should return False."""
        assert validate_file_path(tmp_path) is False


class TestCountLinesSafely:
    """Tests for safe line counting."""

    def test_count_lines_in_existing_file(self, temp_file):
        """Should count lines correctly in existing file."""
        count = count_lines_safely(temp_file)
        # Our fixture has content with newlines
        assert count > 0
        assert count < 20  # Reasonable upper bound

    def test_count_lines_returns_zero_for_permission_error(self, temp_file, caplog):
        """Should return 0 for permission error and log warning."""
        # Make file unreadable
        temp_file.chmod(0o000)

        try:
            count = count_lines_safely(temp_file)
            assert count == 0
            # Should log a warning
            assert any("permission denied" in record.message.lower() for record in caplog.records)
        finally:
            # Restore permissions for cleanup
            temp_file.chmod(0o644)

    def test_count_lines_handles_empty_file(self, tmp_path):
        """Should return 0 for empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        count = count_lines_safely(empty_file)
        assert count == 0

    def test_count_lines_handles_unicode_decode_error(self, tmp_path, caplog):
        """Should handle Unicode decode errors gracefully."""
        # Create file with invalid UTF-8
        bad_file = tmp_path / "bad_encoding.txt"
        bad_file.write_bytes(b'\xff\xfe Invalid UTF-16')

        count = count_lines_safely(bad_file)
        assert count == 0
        # Should log a warning about encoding
        assert any("encoding" in record.message.lower() for record in caplog.records)
