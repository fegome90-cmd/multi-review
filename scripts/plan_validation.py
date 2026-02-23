"""Plan validation utilities for the mr-plan command.

Provides path security checks, prompt injection detection, empty-file
validation, and subagent JSON response schema validation/normalization.
These functions encode the rules described in commands/mr-plan.md and
agents/mr-plan-evaluator.md so that the test suite exercises production
logic rather than inline test helpers.
"""

import re
from typing import Any

# Sensitive path patterns blocked in --file paths (directory prefixes and file patterns)
SENSITIVE_DIRS: list[str] = [".claude/", ".env", ".ssh/", ".git/"]

# Prompt injection patterns to detect in plan content
INJECTION_PATTERNS: list[str] = [
    r"ignore\s+previous\s+instructions?",
    r"act\s+as\s+if\s+you\s+are",
    r"your\s+real\s+task\s+is",
    r"disregard\s+all\s+above",
    r"forget\s+everything",
    r"new\s+instructions?\s*:",
    r"instead\s+of\s+evaluating",
]

# Valid severity values for subagent findings
VALID_SEVERITIES: frozenset[str] = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})

# Required fields in the findings summary block
SUMMARY_FIELDS: list[str] = ["total", "critical", "high", "medium", "low"]


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------

def is_invalid_path(path: str) -> bool:
    """Return True if *path* should be rejected for security reasons.

    Blocks path traversal (``..``), absolute paths (``/`` or ``~``), and
    paths that reference sensitive directories (see ``SENSITIVE_DIRS``).
    """
    if ".." in path:
        return True
    if path.startswith("/") or path.startswith("~"):
        return True
    for pattern in SENSITIVE_DIRS:
        if pattern in path:
            return True
    return False


# ---------------------------------------------------------------------------
# Prompt injection detection
# ---------------------------------------------------------------------------

def detects_injection(content: str) -> bool:
    """Return True if *content* contains prompt injection patterns."""
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def sanitize_content(content: str) -> str:
    """Replace injection patterns in *content* with ``[SANITIZED]``."""
    sanitized = content
    for pattern in INJECTION_PATTERNS:
        sanitized = re.sub(pattern, "[SANITIZED]", sanitized, flags=re.IGNORECASE)
    return sanitized


# ---------------------------------------------------------------------------
# Empty / binary file detection
# ---------------------------------------------------------------------------

def is_empty_content(content: str) -> bool:
    """Return True if *content* is empty or contains only whitespace."""
    return len(content) == 0 or content.strip() == ""


def is_binary_content(content: str) -> bool:
    """Return True if *content* contains binary data (NUL bytes)."""
    return "\x00" in content


# ---------------------------------------------------------------------------
# Subagent JSON response validation and normalization
# ---------------------------------------------------------------------------

def validate_response(response: dict[str, Any]) -> list[str]:
    """Validate a subagent JSON response against the mr-plan schema.

    Returns a (possibly empty) list of human-readable error strings.
    """
    errors: list[str] = []

    if "agent" not in response or not response["agent"]:
        errors.append("Missing or empty 'agent' field")

    if "findings" not in response:
        errors.append("Missing 'findings' field")
    elif not isinstance(response["findings"], list):
        errors.append("'findings' must be an array")

    if "summary" not in response:
        errors.append("Missing 'summary' field")
    else:
        for field in SUMMARY_FIELDS:
            if field not in response["summary"]:
                errors.append(f"Missing summary field: {field}")

    if "confidence" not in response:
        errors.append("Missing 'confidence' field")

    if "findings" in response and isinstance(response["findings"], list):
        for i, finding in enumerate(response["findings"]):
            if "id" not in finding:
                errors.append(f"Finding {i}: missing 'id'")
            elif not re.match(r"^F-\d{3}$", finding.get("id", "")):
                errors.append(f"Finding {i}: invalid 'id' format (must be F-XXX)")

            if "severity" not in finding:
                errors.append(f"Finding {i}: missing 'severity'")
            elif finding.get("severity") not in VALID_SEVERITIES:
                errors.append(f"Finding {i}: invalid severity")

            for field in ["category", "message"]:
                if field not in finding or not finding.get(field):
                    errors.append(f"Finding {i}: missing or empty '{field}'")

    return errors


def normalize_response(response: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized copy of a subagent response.

    Normalizations applied:
    - Severity values are upper-cased.
    - ``confidence`` is clamped to ``[0.0, 1.0]``.
    - Summary count fields are coerced to ``int``.
    """
    normalized = response.copy()

    if "findings" in normalized and isinstance(normalized["findings"], list):
        normalized["findings"] = []
        for finding in response["findings"]:
            norm_finding = finding.copy()
            if "severity" in norm_finding:
                sev = norm_finding["severity"]
                if isinstance(sev, str):
                    norm_finding["severity"] = sev.upper()
                else:
                    norm_finding["severity"] = "UNKNOWN"
            normalized["findings"].append(norm_finding)

    if "confidence" in normalized:
        try:
            conf = float(normalized["confidence"])
        except (ValueError, TypeError):
            conf = 0.0
        normalized["confidence"] = max(0.0, min(1.0, conf))

    if "summary" in normalized:
        normalized["summary"] = {}
        for key in SUMMARY_FIELDS:
            val = response["summary"].get(key, 0)
            try:
                normalized["summary"][key] = int(val)
            except (ValueError, TypeError):
                normalized["summary"][key] = 0

    return normalized
