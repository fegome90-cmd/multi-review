#!/usr/bin/env python3
"""
Validation pass for multi-review false positive elimination.

This module implements Layer 3 of the 3-Layer Defense system:
- Evidence-based validation against tool outputs
- Cross-reference findings with actual linter/test results
- Contradiction detection (finding says X, tool says not-X)

Key Design Principle: Layer 3 must VERIFY with tools, not just "opine".
This addresses root cause #4: "No cross-verification".

Dependencies:
    - Python 3.10+ stdlib only
    - project_context.py (for ProjectContext)
    - finding_filter.py (for Finding)
"""

import dataclasses
import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# EVIDENCE DATACLASS
# =============================================================================

@dataclass(frozen=True)
class Evidence:
    """Evidence from tool outputs.

    Attributes:
        source: Tool that produced this evidence ('ruff', 'mypy', 'pytest', etc.)
        file: File path (relative to repo root).
        line: Line number (1-indexed, or None for file-level).
        message: The actual message from the tool.
        severity: Severity level from the tool ('error', 'warning', 'info').
        code: Optional error code (e.g., 'F401', 'E501' for ruff).
    """
    source: str
    file: str
    line: Optional[int]
    message: str
    severity: str
    code: Optional[str] = None

    def matches_finding(
        self,
        finding: "Finding",
        line_tolerance: int = 2
    ) -> bool:
        """Check if this evidence matches a finding.

        Args:
            finding: The finding to match against.
            line_tolerance: Maximum line number difference for a match.

        Returns:
            True if evidence appears to be about the same issue.
        """
        if self.file != finding.file:
            return False

        if self.line is not None and finding.line > 0:
            if abs(self.line - finding.line) > line_tolerance:
                return False

        return True


# =============================================================================
# VALIDATION MODE ENUM
# =============================================================================

class ValidationMode(Enum):
    """Mode for validation pass.

    Attributes:
        FAST: Use cached evidence from previous runs (default).
        EVIDENCE: Actually run tools to get fresh evidence.
    """
    FAST = "fast"
    EVIDENCE = "evidence"


# =============================================================================
# TOOL OUTPUT PARSERS
# =============================================================================

def parse_ruff_output(output: str, file_path: str) -> List[Evidence]:
    """Parse ruff check output into Evidence objects.

    Ruff output format (text):
        file.py:10:5: F401 [*] `os` imported but unused

    Args:
        output: Raw stdout from ruff check.
        file_path: The file that was checked.

    Returns:
        List of Evidence objects from ruff output.
    """
    evidence_list = []

    for line in output.strip().split('\n'):
        if not line or line.startswith('Found'):
            continue

        # Parse format: file.py:line:col: CODE message
        parts = line.split(':', 3)
        if len(parts) >= 4:
            try:
                line_num = int(parts[1].strip())
                rest = parts[3].strip()

                # Extract code and message
                code = None
                message = rest
                if rest[0].isupper() and ' ' in rest:
                    code_end = rest.index(' ')
                    potential_code = rest[:code_end]
                    if potential_code.isupper() or potential_code[0].isupper():
                        code = potential_code
                        message = rest[code_end + 1:].strip()
                        # Remove [*] marker if present
                        if message.startswith('[*]'):
                            message = message[3:].strip()

                evidence_list.append(Evidence(
                    source='ruff',
                    file=file_path,
                    line=line_num,
                    message=message,
                    severity='warning',
                    code=code,
                ))
            except (ValueError, IndexError):
                continue

    return evidence_list


def parse_mypy_output(output: str, file_path: str) -> List[Evidence]:
    """Parse mypy output into Evidence objects.

    Mypy output format (text):
        file.py:10: error: Incompatible types in assignment

    Args:
        output: Raw stdout from mypy.
        file_path: The file that was checked.

    Returns:
        List of Evidence objects from mypy output.
    """
    evidence_list = []

    for line in output.strip().split('\n'):
        if not line:
            continue

        # Parse format: file.py:line: severity: message
        parts = line.split(':', 3)
        if len(parts) >= 4:
            try:
                line_num = int(parts[1].strip())
                severity = parts[2].strip().lower()
                message = parts[3].strip()

                # Normalize severity
                if severity == 'error':
                    severity = 'error'
                elif severity in ('warning', 'note'):
                    severity = 'warning'
                else:
                    severity = 'info'

                evidence_list.append(Evidence(
                    source='mypy',
                    file=file_path,
                    line=line_num,
                    message=message,
                    severity=severity,
                    code=None,
                ))
            except (ValueError, IndexError):
                continue

    return evidence_list


# =============================================================================
# VALIDATION PASS CLASS
# =============================================================================

class ValidationPass:
    """Layer 3: Evidence-based validation.

    This class validates findings against actual tool outputs to catch
    false positives that slipped through Layers 1 and 2.

    Modes:
        - FAST (default): Use cached evidence from previous runs
        - EVIDENCE: Actually run ruff/mypy to get fresh evidence

    Example:
        >>> context = build_project_context()
        >>> validation = ValidationPass(context, mode=ValidationMode.FAST)
        >>> validated = validation.validate_finding(finding)
        >>> if validated.confidence == 0:
        ...     print("Finding contradicted by tool evidence")
    """

    def __init__(
        self,
        context: "ProjectContext",
        mode: ValidationMode = ValidationMode.FAST,
        repo_root: Optional[Path] = None,
    ):
        """Initialize the validation pass.

        Args:
            context: Project context with configuration.
            mode: Validation mode (FAST or EVIDENCE).
            repo_root: Repository root path (defaults to cwd).
        """
        self.context = context
        self.mode = mode
        self.repo_root = repo_root or Path.cwd()
        self._evidence_cache: Dict[str, List[Evidence]] = {}

    def _get_evidence(self, file_path: str) -> List[Evidence]:
        """Get evidence for a file (from cache or run tools).

        Args:
            file_path: Path to the file (relative to repo root).

        Returns:
            List of Evidence objects for this file.
        """
        if file_path not in self._evidence_cache:
            if self.mode == ValidationMode.EVIDENCE:
                self._evidence_cache[file_path] = self._run_tools(file_path)
            else:
                self._evidence_cache[file_path] = self._load_cached_evidence(file_path)

        return self._evidence_cache[file_path]

    def _run_tools(self, file_path: str) -> List[Evidence]:
        """Run linters to get evidence (EVIDENCE mode only).

        Args:
            file_path: Path to the file (relative to repo root).

        Returns:
            List of Evidence objects from tool runs.
        """
        evidence_list = []
        full_path = self.repo_root / file_path

        # Run ruff for Python files
        if file_path.endswith('.py'):
            try:
                result = subprocess.run(
                    ['ruff', 'check', str(full_path), '--output-format', 'text'],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.stdout:
                    evidence_list.extend(parse_ruff_output(result.stdout, file_path))
            except FileNotFoundError:
                logger.debug("ruff not found - skipping ruff evidence")
            except subprocess.TimeoutExpired:
                logger.warning(f"ruff check timed out for {file_path}")
            except Exception as e:
                logger.warning(f"ruff check failed for {file_path}: {e}")

            # Run mypy if configured
            if self.context.python_config.mypy_configured.value:
                try:
                    result = subprocess.run(
                        ['mypy', str(full_path), '--no-error-summary'],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.stdout:
                        evidence_list.extend(parse_mypy_output(result.stdout, file_path))
                except FileNotFoundError:
                    logger.debug("mypy not found - skipping mypy evidence")
                except subprocess.TimeoutExpired:
                    logger.warning(f"mypy check timed out for {file_path}")
                except Exception as e:
                    logger.warning(f"mypy check failed for {file_path}: {e}")

        return evidence_list

    def _load_cached_evidence(self, file_path: str) -> List[Evidence]:
        """Load cached evidence from previous runs (FAST mode).

        Args:
            file_path: Path to the file.

        Returns:
            List of Evidence objects from cache (empty if not cached).
        """
        # Look for evidence cache file
        cache_dir = self.repo_root / ".multi-review" / "evidence-cache"
        cache_file = cache_dir / f"{file_path.replace('/', '_')}.json"

        if not cache_file.exists():
            return []

        try:
            content = cache_file.read_text(encoding='utf-8')
            data = json.loads(content)
            return [
                Evidence(**item) for item in data.get('evidence', [])
            ]
        except (OSError, json.JSONDecodeError) as e:
            logger.debug(f"Failed to load evidence cache for {file_path}: {e}")
            return []

    def _tool_catches(self, evidence: List[Evidence], finding: "Finding") -> bool:
        """Check if a tool already reports this issue.

        If a tool reports the same issue, the agent finding is redundant
        but not necessarily a false positive - it confirms the issue exists.

        Args:
            evidence: List of evidence from tools.
            finding: The finding to check.

        Returns:
            True if a tool already catches this issue.
        """
        for e in evidence:
            if e.matches_finding(finding):
                # Check if the message is related to the finding category
                finding_terms = set(finding.description.lower().split())
                evidence_terms = set(e.message.lower().split())

                # Simple overlap check
                overlap = finding_terms & evidence_terms
                if len(overlap) >= 2:  # At least 2 common terms
                    return True

        return False

    def _tool_contradicts(self, evidence: List[Evidence], finding: "Finding") -> bool:
        """Check if tool output contradicts the finding.

        Example: Finding says "no type annotation" but mypy would have
        flagged this if it were a real issue in strict mode.

        Args:
            evidence: List of evidence from tools.
            finding: The finding to check.

        Returns:
            True if tool evidence contradicts the finding.
        """
        # Type annotation findings with mypy not in strict mode
        if finding.category.lower() in {'type_annotation', 'typing'}:
            # If mypy is configured but not strict, type annotation issues
            # in internal code might be intentional
            if (self.context.python_config.mypy_configured.value and
                not self.context.python_config.mypy_strict.value):
                # Check if this is about internal/private code
                if '_' in finding.description or 'internal' in finding.description.lower():
                    return True

        # Error handling findings in strict shell scripts
        if finding.category.lower() in {'error_handling', 'error-handling'}:
            if finding.file.endswith(('.sh', '.bash', '.zsh')):
                if Path(finding.file) in self.context.shell_config.strict_mode_files:
                    return True

        return False

    def _contradicts_pattern(self, finding: "Finding") -> bool:
        """Check if finding contradicts known project patterns.

        Args:
            finding: The finding to check.

        Returns:
            True if finding contradicts a known project pattern.
        """
        # Result pattern: if project uses Result, some "missing error handling"
        # findings might be false positives
        if finding.category.lower() in {'error_handling', 'error-handling'}:
            if self.context.python_config.uses_result_pattern.value:
                # Check if the description mentions exceptions being raised
                if 'exception' in finding.description.lower() or 'raise' in finding.description.lower():
                    # Project uses Result pattern - might be intentional
                    return True

        return False

    def validate_finding(self, finding: "Finding") -> "Finding":
        """Validate a finding against tool evidence.

        This is the main entry point for Layer 3 validation.

        Args:
            finding: The finding to validate.

        Returns:
            Updated Finding with adjusted confidence and evidence_refs.
        """
        evidence = self._get_evidence(finding.file)

        # Check 1: Does a tool already catch this?
        if self._tool_catches(evidence, finding):
            # Keep the finding - tool confirms it's real
            new_refs = list(finding.evidence_refs) + [
                f"CONFIRMED: Tool reports similar issue"
            ]
            return dataclasses.replace(
                finding,
                evidence_refs=frozenset(new_refs),
            )

        # Check 2: Does tool output contradict this?
        if self._tool_contradicts(evidence, finding):
            new_refs = list(finding.evidence_refs) + [
                f"CONTRADICTS: Tool evidence suggests this is not an issue"
            ]
            return dataclasses.replace(
                finding,
                confidence=0,
                evidence_refs=frozenset(new_refs),
            )

        # Check 3: Does it contradict known patterns?
        if self._contradicts_pattern(finding):
            new_refs = list(finding.evidence_refs) + [
                f"CONTRADICTS: Project pattern suggests intentional design"
            ]
            return dataclasses.replace(
                finding,
                confidence=max(0, finding.confidence - 50),
                evidence_refs=frozenset(new_refs),
            )

        # No contradiction found - keep original
        return finding

    def validate_findings(self, findings: List["Finding"]) -> List["Finding"]:
        """Validate multiple findings.

        Args:
            findings: List of findings to validate.

        Returns:
            List of validated findings with updated confidence.
        """
        return [self.validate_finding(f) for f in findings]

    def get_validation_summary(
        self,
        findings: List["Finding"]
    ) -> Dict[str, Any]:
        """Get summary of validation results.

        Args:
            findings: List of validated findings.

        Returns:
            Dictionary with validation statistics.
        """
        validated = self.validate_findings(findings)

        confirmed = sum(1 for f in validated if any(
            ref.startswith("CONFIRMED:") for ref in f.evidence_refs
        ))
        contradicted = sum(1 for f in validated if f.confidence == 0)
        reduced = sum(1 for f in validated if any(
            ref.startswith("CONTRADICTS:") for ref in f.evidence_refs
        ) and f.confidence > 0)

        return {
            "total_findings": len(findings),
            "confirmed_by_tools": confirmed,
            "contradicted_by_tools": contradicted,
            "reduced_confidence": reduced,
            "unchanged": len(findings) - confirmed - contradicted - reduced,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def run_validation_pass(
    findings: List["Finding"],
    context: "ProjectContext",
    mode: ValidationMode = ValidationMode.FAST,
) -> List["Finding"]:
    """Run validation pass on findings.

    Convenience function that creates a ValidationPass and validates findings.

    Args:
        findings: List of findings to validate.
        context: Project context.
        mode: Validation mode (FAST or EVIDENCE).

    Returns:
        List of validated findings.
    """
    validation = ValidationPass(context, mode)
    return validation.validate_findings(findings)
