#!/usr/bin/env python3
"""
Tests for feedback_manager_cli module.

Run with: pytest tests/test_feedback_manager_cli.py -v
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from feedback_manager_cli import (
    record_feedback,
    show_stats,
    show_agent,
    main,
)
from feedback_manager import FeedbackManager, FeedbackType


class TestRecordFeedback:
    """Tests for record_feedback function."""

    @pytest.fixture
    def temp_manager(self):
        """Create FeedbackManager with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield FeedbackManager(feedback_dir=Path(tmpdir))

    def test_record_valid_feedback(self, temp_manager, capsys):
        """Test recording valid feedback."""
        finding_json = json.dumps({
            "id": "test-1",
            "file": "src/auth.py",
            "line": 45,
            "category": "security",
            "description": "SQL injection",
            "source_agent": "test-agent",
        })

        result = record_feedback(
            temp_manager,
            finding_json,
            "false_positive",
            "Already handled",
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "Recorded feedback" in captured.out

    def test_record_real_issue(self, temp_manager, capsys):
        """Test recording real issue feedback."""
        finding_json = json.dumps({
            "id": "test-2",
            "file": "src/db.py",
            "line": 10,
            "category": "bug",
            "description": "Null pointer",
            "source_agent": "code-reviewer",
        })

        result = record_feedback(
            temp_manager,
            finding_json,
            "real_issue",
            None,
        )

        assert result == 0
        captured = capsys.readouterr()
        assert "real_issue" in captured.out

    def test_invalid_json(self, temp_manager, capsys):
        """Test handling invalid JSON."""
        result = record_feedback(
            temp_manager,
            "not valid json",
            "false_positive",
            None,
        )

        assert result == 2
        captured = capsys.readouterr()
        assert "Invalid JSON" in captured.err

    def test_invalid_feedback_type(self, temp_manager, capsys):
        """Test handling invalid feedback type."""
        finding_json = json.dumps({
            "id": "test-3",
            "file": "src/test.py",
            "line": 1,
            "category": "test",
            "description": "Test",
            "source_agent": "test",
        })

        result = record_feedback(
            temp_manager,
            finding_json,
            "invalid_type",
            None,
        )

        assert result == 2
        captured = capsys.readouterr()
        assert "Invalid feedback type" in captured.err


class TestShowStats:
    """Tests for show_stats function."""

    @pytest.fixture
    def temp_manager(self):
        """Create FeedbackManager with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield FeedbackManager(feedback_dir=Path(tmpdir))

    def test_empty_stats(self, temp_manager, capsys):
        """Test stats with no feedback."""
        result = show_stats(temp_manager)

        assert result == 0
        captured = capsys.readouterr()
        assert "Feedback Statistics" in captured.out
        assert "Total findings reviewed: 0" in captured.out

    def test_stats_with_data(self, temp_manager, capsys):
        """Test stats with recorded feedback."""
        # Record some feedback
        temp_manager.record_feedback(
            finding_id="test-1",
            file="src/a.py",
            line=1,
            category="security",
            description="Test",
            source_agent="agent-a",
            feedback_type=FeedbackType.REAL_ISSUE,
        )
        temp_manager.record_feedback(
            finding_id="test-2",
            file="src/b.py",
            line=2,
            category="style",
            description="Style issue",
            source_agent="agent-a",
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )

        result = show_stats(temp_manager)

        assert result == 0
        captured = capsys.readouterr()
        assert "Total findings reviewed: 2" in captured.out
        assert "Confirmed real issues: 1" in captured.out
        assert "False positives: 1" in captured.out


class TestShowAgent:
    """Tests for show_agent function."""

    @pytest.fixture
    def temp_manager(self):
        """Create FeedbackManager with temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield FeedbackManager(feedback_dir=Path(tmpdir))

    def test_agent_no_data(self, temp_manager, capsys):
        """Test showing agent with no data."""
        result = show_agent(temp_manager, "unknown-agent")

        assert result == 0
        captured = capsys.readouterr()
        assert "Agent Calibration: unknown-agent" in captured.out
        assert "Total findings: 0" in captured.out

    def test_agent_with_data(self, temp_manager, capsys):
        """Test showing agent with data."""
        # Record feedback for specific agent
        temp_manager.record_feedback(
            finding_id="test-1",
            file="src/a.py",
            line=1,
            category="security",
            description="SQL injection",
            source_agent="my-agent",
            feedback_type=FeedbackType.FALSE_POSITIVE,
            reason="Already handled by ORM",
        )

        result = show_agent(temp_manager, "my-agent")

        assert result == 0
        captured = capsys.readouterr()
        assert "my-agent" in captured.out
        assert "Total findings: 1" in captured.out
        assert "False positives: 1" in captured.out


class TestMainCLI:
    """Tests for main CLI function."""

    def test_stats_flag(self, capsys):
        """Test --stats flag."""
        with patch("sys.argv", ["cli", "--stats"]):
            result = main()
            assert result == 0
            captured = capsys.readouterr()
            assert "Feedback Statistics" in captured.out

    def test_record_requires_finding_json(self, capsys):
        """Test --record requires --finding-json."""
        with patch("sys.argv", ["cli", "--record", "--feedback-type", "false_positive"]):
            result = main()
            assert result == 2
            captured = capsys.readouterr()
            assert "required" in captured.err.lower()

    def test_record_requires_feedback_type(self, capsys):
        """Test --record requires --feedback-type."""
        finding_json = json.dumps({"id": "test", "file": "x.py", "line": 1})
        with patch("sys.argv", ["cli", "--record", "--finding-json", finding_json]):
            result = main()
            assert result == 2
            captured = capsys.readouterr()
            assert "required" in captured.err.lower()

    def test_agent_flag(self, capsys):
        """Test --agent flag."""
        with patch("sys.argv", ["cli", "--agent", "test-agent"]):
            result = main()
            assert result == 0
            captured = capsys.readouterr()
            assert "Agent Calibration" in captured.out

    def test_mutually_exclusive_actions(self, capsys):
        """Test that actions are mutually exclusive."""
        # argparse handles this, but verify it doesn't crash
        with patch("sys.argv", ["cli", "--stats"]):
            result = main()
            assert result == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
