#!/usr/bin/env python3
"""
Tests for feedback_manager module.

Run with: pytest tests/test_feedback_manager.py -v
"""

import sys
import tempfile
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from feedback_manager import (
    FeedbackType,
    FeedbackEntry,
    AgentCalibration,
    FeedbackManager,
)


class TestFeedbackType:
    """Tests for FeedbackType enum."""

    def test_all_types_exist(self):
        """Test all expected types exist."""
        assert FeedbackType.REAL_ISSUE.value == "real_issue"
        assert FeedbackType.FALSE_POSITIVE.value == "false_positive"
        assert FeedbackType.ALREADY_FIXED.value == "already_fixed"
        assert FeedbackType.NOT_ACTIONABLE.value == "not_actionable"

    def test_from_string(self):
        """Test creating from string."""
        assert FeedbackType("real_issue") == FeedbackType.REAL_ISSUE
        assert FeedbackType("false_positive") == FeedbackType.FALSE_POSITIVE


class TestFeedbackEntry:
    """Tests for FeedbackEntry dataclass."""

    def test_create_entry(self):
        """Test creating a feedback entry."""
        entry = FeedbackEntry(
            feedback_id="fb-20260213-120000-abc123",
            timestamp="2026-02-13T12:00:00",
            finding_id="test-1",
            file="src/auth.py",
            line=45,
            category="security",
            description="SQL injection",
            source_agent="test-agent",
            feedback_type=FeedbackType.FALSE_POSITIVE,
            reason="Already handled",
        )

        assert entry.feedback_id == "fb-20260213-120000-abc123"
        assert entry.feedback_type == FeedbackType.FALSE_POSITIVE
        assert entry.reason == "Already handled"

    def test_to_dict(self):
        """Test serialization to dict."""
        entry = FeedbackEntry(
            feedback_id="fb-test",
            timestamp="2026-02-13T12:00:00",
            finding_id="test-1",
            file="src/auth.py",
            line=45,
            category="security",
            description="Test",
            source_agent="agent",
            feedback_type=FeedbackType.REAL_ISSUE,
        )

        data = entry.to_dict()
        assert data["feedback_id"] == "fb-test"
        assert data["feedback_type"] == "real_issue"
        assert data["file"] == "src/auth.py"

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "feedback_id": "fb-test",
            "timestamp": "2026-02-13T12:00:00",
            "finding_id": "test-1",
            "file": "src/auth.py",
            "line": 45,
            "category": "security",
            "description": "Test",
            "source_agent": "agent",
            "feedback_type": "false_positive",
            "reason": "Test reason",
        }

        entry = FeedbackEntry.from_dict(data)
        assert entry.feedback_id == "fb-test"
        assert entry.feedback_type == FeedbackType.FALSE_POSITIVE
        assert entry.reason == "Test reason"


class TestAgentCalibration:
    """Tests for AgentCalibration dataclass."""

    def test_create_calibration(self):
        """Test creating agent calibration."""
        cal = AgentCalibration(
            agent_name="test-agent",
            total_findings=10,
            real_issues=7,
            false_positives=2,
            already_fixed=1,
            not_actionable=0,
        )

        assert cal.agent_name == "test-agent"
        assert cal.total_findings == 10

    def test_accuracy_calculation(self):
        """Test accuracy calculation."""
        cal = AgentCalibration(
            agent_name="test",
            total_findings=10,
            real_issues=7,
            false_positives=3,
        )

        assert cal.accuracy == 0.7
        assert cal.fp_rate == 0.3

    def test_accuracy_zero_findings(self):
        """Test accuracy with zero findings."""
        cal = AgentCalibration(agent_name="test")
        assert cal.accuracy == 0.0
        assert cal.fp_rate == 0.0

    def test_get_confidence_adjustment(self):
        """Test confidence adjustment calculation."""
        cal = AgentCalibration(
            agent_name="test",
            confidence_adjustment=0.8,
        )

        assert cal.get_confidence_adjustment() == 0.8

    def test_get_confidence_adjustment_with_pattern(self):
        """Test confidence adjustment with suppress pattern."""
        cal = AgentCalibration(
            agent_name="test",
            pattern_learnings=[
                {"category": "security", "action": "suppress"}
            ],
        )

        assert cal.get_confidence_adjustment("security") == 0.0

    def test_to_dict_and_from_dict(self):
        """Test serialization round trip."""
        cal = AgentCalibration(
            agent_name="test",
            total_findings=10,
            real_issues=7,
            false_positives=2,
            pattern_learnings=[{"pattern": "test", "count": 3}],
        )

        data = cal.to_dict()
        restored = AgentCalibration.from_dict(data)

        assert restored.agent_name == "test"
        assert restored.total_findings == 10
        assert restored.pattern_learnings == [{"pattern": "test", "count": 3}]


class TestFeedbackManager:
    """Tests for FeedbackManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_initialization(self, temp_dir):
        """Test manager initialization."""
        manager = FeedbackManager(feedback_dir=temp_dir)

        assert manager.feedback_dir == temp_dir
        assert manager.aggregate_dir.exists()

    def test_record_feedback(self, temp_dir):
        """Test recording feedback."""
        manager = FeedbackManager(feedback_dir=temp_dir)

        entry = manager.record_feedback(
            finding_id="test-1",
            file="src/auth.py",
            line=45,
            category="security",
            description="SQL injection risk",
            source_agent="test-agent",
            feedback_type=FeedbackType.FALSE_POSITIVE,
            reason="Already handled by ORM",
        )

        assert entry.finding_id == "test-1"
        assert entry.feedback_type == FeedbackType.FALSE_POSITIVE
        assert "fb-" in entry.feedback_id

    def test_load_calibration(self, temp_dir):
        """Test loading calibration."""
        manager = FeedbackManager(feedback_dir=temp_dir)

        # Record some feedback
        manager.record_feedback(
            finding_id="test-1",
            file="src/a.py",
            line=1,
            category="security",
            description="Test",
            source_agent="agent-a",
            feedback_type=FeedbackType.REAL_ISSUE,
        )

        calibration = manager.load_calibration()

        assert "agent_calibrations" in calibration
        assert "agent-a" in calibration["agent_calibrations"]

    def test_get_agent_calibration(self, temp_dir):
        """Test getting calibration for specific agent."""
        manager = FeedbackManager(feedback_dir=temp_dir)

        # Record feedback for agent-a
        manager.record_feedback(
            finding_id="test-1",
            file="src/a.py",
            line=1,
            category="security",
            description="Test",
            source_agent="agent-a",
            feedback_type=FeedbackType.REAL_ISSUE,
        )

        cal = manager.get_agent_calibration("agent-a")

        assert cal.agent_name == "agent-a"
        assert cal.total_findings == 1
        assert cal.real_issues == 1

    def test_get_stats(self, temp_dir):
        """Test getting statistics."""
        manager = FeedbackManager(feedback_dir=temp_dir)

        # Record multiple feedbacks
        manager.record_feedback(
            finding_id="test-1",
            file="src/a.py",
            line=1,
            category="security",
            description="Test",
            source_agent="agent-a",
            feedback_type=FeedbackType.REAL_ISSUE,
        )
        manager.record_feedback(
            finding_id="test-2",
            file="src/b.py",
            line=2,
            category="style",
            description="Test",
            source_agent="agent-a",
            feedback_type=FeedbackType.FALSE_POSITIVE,
        )

        stats = manager.get_stats()

        assert stats["total_findings_reviewed"] == 2
        assert stats["total_real_issues"] == 1
        assert stats["total_false_positives"] == 1
        assert stats["overall_accuracy"] == 0.5

    def test_pattern_extraction(self, temp_dir):
        """Test pattern extraction from false positives."""
        manager = FeedbackManager(feedback_dir=temp_dir)

        # Record FP with pattern-matchable description
        manager.record_feedback(
            finding_id="test-1",
            file="src/a.py",
            line=1,
            category="security",
            description="SQL injection risk - already handled by ORM",
            source_agent="agent-a",
            feedback_type=FeedbackType.FALSE_POSITIVE,
            reason="Already handled by ORM",
        )

        cal = manager.get_agent_calibration("agent-a")

        # Pattern should be detected
        assert len(cal.pattern_learnings) > 0
        assert cal.pattern_learnings[0]["pattern"] == "sql_orm_handled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
