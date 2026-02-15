#!/usr/bin/env python3
"""
Output envelope for multi-review results.

This module provides the ReviewEnvelope container that separates deterministic
Finding data from runtime metadata, enabling:
- Stable golden snapshots
- Cache invalidation tracking
- Latency measurement
- Degradation handling

Key Design Principle: Finding contains NO timestamp/review_id/schema_version.
These belong in the envelope, not per-finding.

Dependencies:
    - Python 3.10+ stdlib only
    - finding_filter.py (for Finding, FilteredFinding)
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional


class DegradationLevel(Enum):
    """Validation degradation levels.

    Attributes:
        FULL: All validation tools available and working.
        PARTIAL: Some tools unavailable but core validation works.
        DEGRADED: Multiple tools unavailable, validation quality reduced.
        OFFLINE: No validation tools available, using fallback logic only.
    """
    FULL = "full"
    PARTIAL = "partial"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class ToolStatus(Enum):
    """Status of validation tools.

    Attributes:
        SUCCESS: Tool ran successfully.
        TIMEOUT: Tool timed out before completing.
        MISSING: Tool not installed or not found.
        ERROR: Tool crashed or returned unexpected error.
        SKIPPED: Tool not applicable (e.g., mypy on non-Python files).
    """
    SUCCESS = "success"
    TIMEOUT = "timeout"
    MISSING = "missing"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class LatencyMetrics:
    """Latency measurement for review phases.

    Attributes:
        context_ms: Time to build project context (ms).
        filter_ms: Time for Layer 2 filtering (ms).
        validate_ms: Time for Layer 3 validation (ms).
        total_ms: Total review time (ms).
    """
    context_ms: int = 0
    filter_ms: int = 0
    validate_ms: int = 0
    total_ms: int = 0

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for JSON serialization."""
        return {
            "context_ms": self.context_ms,
            "filter_ms": self.filter_ms,
            "validate_ms": self.validate_ms,
            "total_ms": self.total_ms,
        }


@dataclass
class CacheMetrics:
    """Cache performance metrics.

    Attributes:
        hits: Number of cache hits.
        misses: Number of cache misses.
        hit_rate: Cache hit rate (0.0 to 1.0).
    """
    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 3),
        }


@dataclass
class ReviewEnvelope:
    """Container for review output with metadata.

    This separates deterministic Finding data from runtime metadata,
    enabling stable snapshots and proper cache invalidation.

    Attributes:
        schema_version: Version of this envelope schema.
        review_id: Unique identifier for this review (UUID).
        timestamp: ISO 8601 timestamp when review was created.
        findings: List of active (non-suppressed) findings.
        suppressed: List of filtered/suppressed findings with reasons.
        validation_status: Current degradation level of validation.
        tool_status: Status of each validation tool.
        latency: Latency metrics by phase.
        cache: Cache performance metrics.
        summary: Summary statistics (counts by severity, etc.).

    Example:
        >>> envelope = ReviewEnvelope.create(
        ...     findings=[finding1, finding2],
        ...     suppressed=[filtered1],
        ... )
        >>> envelope.to_json()
        '{"schema_version": "1.0.0", ...}'
    """
    schema_version: str = "1.0.0"
    review_id: str = ""
    timestamp: str = ""
    findings: List[Any] = field(default_factory=list)  # List[Finding]
    suppressed: List[Any] = field(default_factory=list)  # List[FilteredFinding]
    validation_status: DegradationLevel = DegradationLevel.FULL
    tool_status: Dict[str, ToolStatus] = field(default_factory=dict)
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)
    cache: CacheMetrics = field(default_factory=CacheMetrics)
    summary: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        findings: List[Any],
        suppressed: List[Any],
        validation_status: DegradationLevel = DegradationLevel.FULL,
        tool_status: Optional[Dict[str, ToolStatus]] = None,
        latency: Optional[LatencyMetrics] = None,
        cache: Optional[CacheMetrics] = None,
        summary: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
        review_id: Optional[str] = None,
    ) -> "ReviewEnvelope":
        """Create a new ReviewEnvelope with generated metadata.

        Args:
            findings: List of active findings.
            suppressed: List of suppressed findings.
            validation_status: Validation degradation level.
            tool_status: Status of validation tools.
            latency: Latency metrics.
            cache: Cache metrics.
            summary: Summary statistics.
            timestamp: Optional fixed timestamp (for testing).
            review_id: Optional fixed review ID (for testing).

        Returns:
            New ReviewEnvelope instance.
        """
        return cls(
            schema_version="1.0.0",
            review_id=review_id or str(uuid.uuid4()),
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            findings=findings,
            suppressed=suppressed,
            validation_status=validation_status,
            tool_status=tool_status or {},
            latency=latency or LatencyMetrics(),
            cache=cache or CacheMetrics(),
            summary=summary or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON.
        """
        return {
            "schema_version": self.schema_version,
            "review_id": self.review_id,
            "timestamp": self.timestamp,
            "findings": [
                self._finding_to_dict(f) for f in self.findings
            ],
            "suppressed": [
                self._filtered_finding_to_dict(f) for f in self.suppressed
            ],
            "validation_status": self.validation_status.value,
            "tool_status": {
                k: v.value for k, v in self.tool_status.items()
            },
            "latency": self.latency.to_dict(),
            "cache": self.cache.to_dict(),
            "summary": self.summary,
        }

    def _finding_to_dict(self, finding: Any) -> Dict[str, Any]:
        """Convert a Finding to dictionary.

        Uses dataclasses.asdict if available, otherwise getattr.
        Converts frozenset to sorted list for JSON serialization.
        """
        try:
            from dataclasses import asdict
            result = asdict(finding)
            # Convert frozenset to sorted list for JSON serialization
            if "evidence_refs" in result and isinstance(result["evidence_refs"], frozenset):
                result["evidence_refs"] = sorted(result["evidence_refs"])
            return result
        except TypeError:
            # Not a dataclass, use manual extraction
            refs = getattr(finding, "evidence_refs", [])
            if isinstance(refs, frozenset):
                refs = sorted(refs)
            return {
                "id": getattr(finding, "id", ""),
                "file": getattr(finding, "file", ""),
                "line": getattr(finding, "line", 0),
                "category": getattr(finding, "category", ""),
                "severity": getattr(finding, "severity", ""),
                "confidence": getattr(finding, "confidence", 0),
                "description": getattr(finding, "description", ""),
                "suggested_fix": getattr(finding, "suggested_fix", None),
                "evidence_refs": list(refs) if not isinstance(refs, list) else refs,
                "source_agent": getattr(finding, "source_agent", "unknown"),
            }

    def _filtered_finding_to_dict(self, filtered: Any) -> Dict[str, Any]:
        """Convert a FilteredFinding to dictionary."""
        finding = getattr(filtered, "finding", None)

        # Handle reason_code enum
        reason_code = getattr(filtered, "reason_code", None)
        reason_code_value = None
        if reason_code is not None:
            if hasattr(reason_code, "value"):
                reason_code_value = reason_code.value
            else:
                reason_code_value = str(reason_code)

        result = {
            "action": getattr(filtered, "action", {}).value if hasattr(filtered, "action") else "unknown",
            "reason": getattr(filtered, "reason", ""),
            "filtered_confidence": getattr(filtered, "filtered_confidence", 0),
            "reason_code": reason_code_value,
            "filter_rule_id": getattr(filtered, "filter_rule_id", None),
        }
        if finding:
            result["finding"] = self._finding_to_dict(finding)
        return result

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string.

        Args:
            indent: JSON indentation level.

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewEnvelope":
        """Create ReviewEnvelope from dictionary.

        Args:
            data: Dictionary representation.

        Returns:
            ReviewEnvelope instance.
        """
        # Import here to avoid circular dependency
        from finding_filter import Finding, FilteredFinding, FilterAction

        # Parse findings
        findings = []
        for f_data in data.get("findings", []):
            if isinstance(f_data, dict):
                # Convert evidence_refs back to frozenset if needed
                if "evidence_refs" in f_data and isinstance(f_data["evidence_refs"], list):
                    f_data["evidence_refs"] = frozenset(f_data["evidence_refs"])
                findings.append(Finding(**f_data))

        # Parse suppressed
        suppressed = []
        for s_data in data.get("suppressed", []):
            if isinstance(s_data, dict):
                finding_data = s_data.get("finding", {})
                if "evidence_refs" in finding_data and isinstance(finding_data["evidence_refs"], list):
                    finding_data["evidence_refs"] = frozenset(finding_data["evidence_refs"])

                suppressed.append(FilteredFinding(
                    finding=Finding(**finding_data) if finding_data else None,
                    action=FilterAction(s_data.get("action", "set_confidence")),
                    reason=s_data.get("reason", ""),
                    filtered_confidence=s_data.get("filtered_confidence", 0),
                ))

        # Parse tool status
        tool_status = {}
        for tool, status in data.get("tool_status", {}).items():
            tool_status[tool] = ToolStatus(status)

        # Parse latency
        latency_data = data.get("latency", {})
        latency = LatencyMetrics(
            context_ms=latency_data.get("context_ms", 0),
            filter_ms=latency_data.get("filter_ms", 0),
            validate_ms=latency_data.get("validate_ms", 0),
            total_ms=latency_data.get("total_ms", 0),
        )

        # Parse cache
        cache_data = data.get("cache", {})
        cache = CacheMetrics(
            hits=cache_data.get("hits", 0),
            misses=cache_data.get("misses", 0),
        )

        return cls(
            schema_version=data.get("schema_version", "1.0.0"),
            review_id=data.get("review_id", ""),
            timestamp=data.get("timestamp", ""),
            findings=findings,
            suppressed=suppressed,
            validation_status=DegradationLevel(data.get("validation_status", "full")),
            tool_status=tool_status,
            latency=latency,
            cache=cache,
            summary=data.get("summary", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ReviewEnvelope":
        """Create ReviewEnvelope from JSON string.

        Args:
            json_str: JSON string representation.

        Returns:
            ReviewEnvelope instance.
        """
        return cls.from_dict(json.loads(json_str))
