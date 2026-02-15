#!/usr/bin/env python3
"""
Tests for schema snapshots and reason code validation.

This module provides:
- Golden snapshot tests for ReviewEnvelope
- Reason code documentation validation
- Finding determinism tests
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional

import pytest

# Import from scripts
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from finding_filter import (
    Finding,
    FilteredFinding,
    FilterAction,
    SuppressionReasonCode,
)
from schemas.output_envelope import (
    ReviewEnvelope,
    DegradationLevel,
    ToolStatus,
    LatencyMetrics,
    CacheMetrics,
)


# =============================================================================
# FIXTURES FOR DETERMINISTIC SNAPSHOTS
# =============================================================================

@pytest.fixture
def fixed_timestamp() -> str:
    """Fixed timestamp for deterministic snapshots."""
    return "2026-01-01T00:00:00Z"


@pytest.fixture
def fixed_review_id() -> str:
    """Fixed review ID for deterministic snapshots."""
    return "review-00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_finding() -> Finding:
    """Sample finding for tests."""
    return Finding(
        id="finding-001",
        file="scripts/example.py",
        line=42,
        category="error_handling",
        severity="Important",
        confidence=75,
        description="Missing error handling for API call",
        suggested_fix="Add try/except block",
        evidence_refs=frozenset(["line_42_api_call"]),
        source_agent="code-reviewer",
    )


@pytest.fixture
def sample_filtered_finding(sample_finding: Finding) -> FilteredFinding:
    """Sample filtered finding for tests."""
    return FilteredFinding(
        finding=sample_finding,
        action=FilterAction.SUPPRESS,
        reason="Shell strict mode already handles this",
        filtered_confidence=0,
        reason_code=SuppressionReasonCode.L2_SHELL_STRICT_MODE,
        filter_rule_id="L2_rule_shell_strict",
    )


# =============================================================================
# FINDING DETERMINISM TESTS
# =============================================================================

class TestFindingDeterminism:
    """Tests for Finding determinism (no metadata in Finding)."""

    def test_finding_equality(self) -> None:
        """Finding without metadata is deterministic - equal instances are equal."""
        f1 = Finding(
            id="1",
            file="test.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
        )
        f2 = Finding(
            id="1",
            file="test.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
        )
        assert f1 == f2

    def test_finding_hash_stability(self) -> None:
        """Finding hash is stable across instances."""
        f1 = Finding(
            id="1",
            file="test.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
        )
        f2 = Finding(
            id="1",
            file="test.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
        )
        assert hash(f1) == hash(f2)

    def test_finding_no_metadata_fields(self) -> None:
        """Finding should NOT have timestamp, review_id, or schema_version."""
        f = Finding(
            id="1",
            file="test.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
        )
        # Finding should not have these metadata fields
        assert not hasattr(f, "timestamp")
        assert not hasattr(f, "review_id")
        assert not hasattr(f, "schema_version")

    def test_finding_json_deterministic(self) -> None:
        """Finding JSON serialization is deterministic."""
        from dataclasses import asdict

        f1 = Finding(
            id="1",
            file="test.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
            evidence_refs=frozenset(["a", "b"]),
        )
        f2 = Finding(
            id="1",
            file="test.py",
            line=10,
            category="style",
            severity="Low",
            confidence=50,
            description="Test finding",
            evidence_refs=frozenset(["b", "a"]),  # Different order
        )

        # Convert frozenset to sorted list for deterministic JSON
        def finding_to_json_dict(f: Finding) -> Dict[str, Any]:
            d = asdict(f)
            d["evidence_refs"] = sorted(d["evidence_refs"])
            return d

        # JSON should be the same regardless of frozenset order
        json1 = json.dumps(finding_to_json_dict(f1), sort_keys=True)
        json2 = json.dumps(finding_to_json_dict(f2), sort_keys=True)
        assert json1 == json2


# =============================================================================
# ENVELOPE SNAPSHOT TESTS
# =============================================================================

class TestEnvelopeSnapshots:
    """Golden snapshot tests for ReviewEnvelope."""

    def test_envelope_deterministic_with_fixed_values(
        self,
        fixed_timestamp: str,
        fixed_review_id: str,
        sample_finding: Finding,
        sample_filtered_finding: FilteredFinding,
    ) -> None:
        """Envelope with fixed values is deterministic."""
        envelope1 = ReviewEnvelope.create(
            findings=[sample_finding],
            suppressed=[sample_filtered_finding],
            validation_status=DegradationLevel.FULL,
            tool_status={"ruff": ToolStatus.SUCCESS, "mypy": ToolStatus.SUCCESS},
            latency=LatencyMetrics(context_ms=10, filter_ms=5, validate_ms=20, total_ms=35),
            cache=CacheMetrics(hits=10, misses=2),
            summary={"total": 2, "suppressed": 1},
            timestamp=fixed_timestamp,
            review_id=fixed_review_id,
        )

        envelope2 = ReviewEnvelope.create(
            findings=[sample_finding],
            suppressed=[sample_filtered_finding],
            validation_status=DegradationLevel.FULL,
            tool_status={"ruff": ToolStatus.SUCCESS, "mypy": ToolStatus.SUCCESS},
            latency=LatencyMetrics(context_ms=10, filter_ms=5, validate_ms=20, total_ms=35),
            cache=CacheMetrics(hits=10, misses=2),
            summary={"total": 2, "suppressed": 1},
            timestamp=fixed_timestamp,
            review_id=fixed_review_id,
        )

        json1 = envelope1.to_json()
        json2 = envelope2.to_json()
        assert json1 == json2

    def test_envelope_json_structure(
        self,
        fixed_timestamp: str,
        fixed_review_id: str,
        sample_finding: Finding,
    ) -> None:
        """Envelope JSON has expected structure."""
        envelope = ReviewEnvelope.create(
            findings=[sample_finding],
            suppressed=[],
            timestamp=fixed_timestamp,
            review_id=fixed_review_id,
        )

        data = json.loads(envelope.to_json())

        assert data["schema_version"] == "1.0.0"
        assert data["review_id"] == fixed_review_id
        assert data["timestamp"] == fixed_timestamp
        assert len(data["findings"]) == 1
        assert data["findings"][0]["id"] == "finding-001"
        assert data["validation_status"] == "full"
        assert "latency" in data
        assert "cache" in data

    def test_envelope_serialization_roundtrip(
        self,
        sample_finding: Finding,
        sample_filtered_finding: FilteredFinding,
    ) -> None:
        """Envelope can be serialized and deserialized."""
        original = ReviewEnvelope.create(
            findings=[sample_finding],
            suppressed=[sample_filtered_finding],
            validation_status=DegradationLevel.PARTIAL,
            tool_status={"ruff": ToolStatus.SUCCESS},
        )

        json_str = original.to_json()
        restored = ReviewEnvelope.from_json(json_str)

        assert restored.schema_version == original.schema_version
        assert restored.validation_status == original.validation_status
        assert len(restored.findings) == len(original.findings)
        assert len(restored.suppressed) == len(original.suppressed)


# =============================================================================
# REASON CODE VALIDATION
# =============================================================================

class TestReasonCodes:
    """Tests for reason code validation."""

    def test_all_reason_codes_documented(self) -> None:
        """All reason codes must be documented in REASON_CODES.md."""
        # Path to docs
        docs_path = Path(__file__).parent.parent / "docs" / "REASON_CODES.md"
        assert docs_path.exists(), "REASON_CODES.md must exist"

        docs_content = docs_path.read_text()

        # Get all reason codes
        all_codes = list(SuppressionReasonCode)

        for code in all_codes:
            assert code.value in docs_content, (
                f"Reason code {code.value} must be documented in REASON_CODES.md"
            )

    def test_all_reason_codes_have_l2_or_l3_prefix(self) -> None:
        """All reason codes must have L2_ or L3_ prefix."""
        for code in SuppressionReasonCode:
            assert code.value.startswith("L2_") or code.value.startswith("L3_"), (
                f"Reason code {code.value} must have L2_ or L3_ prefix"
            )

    def test_reason_code_count(self) -> None:
        """Verify expected number of reason codes."""
        l2_codes = [c for c in SuppressionReasonCode if c.value.startswith("L2_")]
        l3_codes = [c for c in SuppressionReasonCode if c.value.startswith("L3_")]

        # Should have at least these L2 codes
        expected_l2 = {
            SuppressionReasonCode.L2_SHELL_STRICT_MODE,
            SuppressionReasonCode.L2_STYLE_NITPICK,
            SuppressionReasonCode.L2_INTERNAL_HELPER,
            SuppressionReasonCode.L2_MYPY_NOT_STRICT,
            SuppressionReasonCode.L2_LOW_VALUE,
            SuppressionReasonCode.L2_TOOL_ALREADY_CATCHES,
            SuppressionReasonCode.L2_OPTIONAL_ENHANCEMENT,
            SuppressionReasonCode.L2_PRE_EXISTING_CODE,
            SuppressionReasonCode.L2_LEARNED_PATTERN,
        }
        assert expected_l2.issubset(set(l2_codes))

        # Should have at least these L3 codes
        expected_l3 = {
            SuppressionReasonCode.L3_NO_EVIDENCE_MATCH,
            SuppressionReasonCode.L3_VALIDATION_CONTRADICTED,
            SuppressionReasonCode.L3_TOOL_TIMEOUT,
            SuppressionReasonCode.L3_TOOL_MISSING,
        }
        assert expected_l3.issubset(set(l3_codes))


# =============================================================================
# BACKWARD COMPATIBILITY
# =============================================================================

class TestBackwardCompatibility:
    """Tests for backward compatibility."""

    def test_filtered_finding_optional_fields(self, sample_finding: Finding) -> None:
        """FilteredFinding should work with and without reason_code/rule_id."""
        # Old-style (without new fields)
        old_style = FilteredFinding(
            finding=sample_finding,
            action=FilterAction.SUPPRESS,
            reason="Test reason",
            filtered_confidence=0,
        )

        # New-style (with new fields)
        new_style = FilteredFinding(
            finding=sample_finding,
            action=FilterAction.SUPPRESS,
            reason="Test reason",
            filtered_confidence=0,
            reason_code=SuppressionReasonCode.L2_SHELL_STRICT_MODE,
            filter_rule_id="L2_rule_shell_strict",
        )

        # Both should work
        assert old_style.is_suppressed
        assert new_style.is_suppressed
        assert old_style.reason_code is None
        assert new_style.reason_code == SuppressionReasonCode.L2_SHELL_STRICT_MODE


# =============================================================================
# TOOL STATUS TESTS
# =============================================================================

class TestToolStatus:
    """Tests for ToolStatus enum."""

    def test_tool_status_values(self) -> None:
        """ToolStatus has expected values."""
        assert ToolStatus.SUCCESS.value == "success"
        assert ToolStatus.TIMEOUT.value == "timeout"
        assert ToolStatus.MISSING.value == "missing"
        assert ToolStatus.ERROR.value == "error"
        assert ToolStatus.SKIPPED.value == "skipped"

    def test_skipped_status_exists(self) -> None:
        """SKIPPED status must exist for non-applicable tools."""
        assert hasattr(ToolStatus, "SKIPPED")


# =============================================================================
# LATENCY AND CACHE METRICS
# =============================================================================

class TestMetrics:
    """Tests for latency and cache metrics."""

    def test_latency_metrics_to_dict(self) -> None:
        """LatencyMetrics serializes correctly."""
        metrics = LatencyMetrics(context_ms=10, filter_ms=5, validate_ms=20, total_ms=35)
        data = metrics.to_dict()

        assert data["context_ms"] == 10
        assert data["filter_ms"] == 5
        assert data["validate_ms"] == 20
        assert data["total_ms"] == 35

    def test_cache_metrics_hit_rate(self) -> None:
        """CacheMetrics calculates hit rate correctly."""
        # 10 hits, 0 misses = 100% hit rate
        m1 = CacheMetrics(hits=10, misses=0)
        assert m1.hit_rate == 1.0

        # 10 hits, 10 misses = 50% hit rate
        m2 = CacheMetrics(hits=10, misses=10)
        assert m2.hit_rate == 0.5

        # 0 hits, 0 misses = 0% hit rate (edge case)
        m3 = CacheMetrics(hits=0, misses=0)
        assert m3.hit_rate == 0.0

    def test_cache_metrics_to_dict(self) -> None:
        """CacheMetrics serializes correctly."""
        metrics = CacheMetrics(hits=10, misses=2)
        data = metrics.to_dict()

        assert data["hits"] == 10
        assert data["misses"] == 2
        # hit_rate is rounded to 3 decimal places
        assert abs(data["hit_rate"] - (10 / 12)) < 0.001
