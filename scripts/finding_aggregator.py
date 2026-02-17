#!/usr/bin/env python3
"""
Finding aggregator for multi-review command.

This script converts agent outputs to Finding objects and applies
3-Layer Defense filtering (Layer 2: FindingFilter, Layer 3: ValidationPass).

Usage:
    python3 finding_aggregator.py --context-json <context.json> --findings-dir <dir>
    python3 finding_aggregator.py --context-json <context.json> --findings-json <findings.json>

Dependencies:
    - Python 3.10+ stdlib only
    - finding_filter.py
    - validation_pass.py
    - project_context.py
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from finding_filter import (
    Finding,
    FindingFilter,
    FilterAction,
    FilteredFinding,
)
from project_context import ProjectContext
from validation_pass import ValidationPass, ValidationMode
from xml_finding_parser import parse_xml_findings, has_xml_findings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# FINDING PARSING
# =============================================================================


def parse_severity(severity_str: str) -> str:
    """Normalize severity string."""
    severity_map = {
        "critical": "Critical",
        "important": "Important",
        "high": "Important",
        "medium": "Important",
        "low": "Low",
        "suggestion": "Low",
        "info": "Low",
    }
    return severity_map.get(severity_str.lower(), "Low")


def parse_confidence(confidence_str: str) -> int:
    """Parse confidence from string or number."""
    if isinstance(confidence_str, (int, float)):
        return int(confidence_str)

    if isinstance(confidence_str, str):
        # Try to extract number
        match = re.search(r"(\d+)", confidence_str)
        if match:
            return int(match.group(1))

        # Word-based confidence
        word_map = {
            "certain": 100,
            "high": 75,
            "medium": 50,
            "low": 25,
            "none": 0,
        }
        for word, value in word_map.items():
            if word in confidence_str.lower():
                return value

    return 50  # Default medium confidence


def parse_agent_output(agent_name: str, output: str) -> List[Finding]:
    """Parse agent output text into Finding objects.

    Tries XML parsing first, falls back to regex patterns.

    Args:
        agent_name: Name of the agent that produced the output.
        output: Raw output text from the agent.

    Returns:
        List of Finding objects extracted from the output.
    """
    # Try XML parsing first (more robust)
    if has_xml_findings(output):
        xml_findings = parse_xml_findings(output, agent_name)
        if xml_findings:
            logger.info(
                f"Successfully parsed {len(xml_findings)} XML findings from {agent_name}"
            )
            return xml_findings

    # Fall back to regex parsing
    logger.debug(f"No XML findings found for {agent_name}, using regex fallback")
    return _parse_regex_findings(agent_name, output)


def _parse_regex_findings(agent_name: str, output: str) -> List[Finding]:
    """Parse agent output using regex patterns (legacy fallback).

    Args:
        agent_name: Name of the agent that produced the output.
        output: Raw output text from the agent.

    Returns:
        List of Finding objects extracted from the output.
    """
    findings = []

    # Pattern 1: Markdown table rows | file | line | severity | description |
    table_pattern = re.compile(
        r"\|\s*`?([^`|\n]+)`?\s*\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*([^|\n]+)\s*\|"
    )

    # Pattern 2: File:line format with severity
    file_line_pattern = re.compile(
        r"([^\s:]+\.py):(\d+)(?::\d+)?:?\s*\[?(\w+)\]?\s*[-:]?\s*(.+)"
    )

    # Pattern 3: Severity heading followed by bullet points
    severity_section = re.compile(
        r"###?\s*(Critical|Important|Low|Suggestion)s?\s*\n(.*?)(?=###|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    # Pattern 4: Bullet point with file reference
    bullet_pattern = re.compile(
        r"[-*]\s*\[([^\]]+)\][\s:]*([^\s:]+):(\d+)[\s:]*[(-]?\s*(\d+)%?\s*[)-]?\s*[-:]?\s*(.+)"
    )

    finding_id = 0

    # Try each pattern
    for match in table_pattern.finditer(output):
        finding_id += 1
        file_path, line, severity, description = match.groups()
        findings.append(
            Finding(
                id=f"{agent_name}-{finding_id}",
                file=file_path.strip(),
                line=int(line),
                category="general",
                severity=parse_severity(severity),
                confidence=50,
                description=description.strip(),
                evidence_refs=frozenset([agent_name]),
                source_agent=agent_name,
            )
        )

    for match in file_line_pattern.finditer(output):
        finding_id += 1
        file_path, line, severity, description = match.groups()
        findings.append(
            Finding(
                id=f"{agent_name}-{finding_id}",
                file=file_path.strip(),
                line=int(line),
                category="general",
                severity=parse_severity(severity),
                confidence=50,
                description=description.strip(),
                evidence_refs=frozenset([agent_name]),
                source_agent=agent_name,
            )
        )

    for match in bullet_pattern.finditer(output):
        finding_id += 1
        agent, file_path, line, confidence, description = match.groups()
        findings.append(
            Finding(
                id=f"{agent_name}-{finding_id}",
                file=file_path.strip(),
                line=int(line),
                category="general",
                severity="Important",  # Default to important if not specified
                confidence=parse_confidence(confidence),
                description=description.strip(),
                evidence_refs=frozenset([agent_name]),
                source_agent=agent_name,
            )
        )

    # If no structured findings found, try to extract from sections
    if not findings:
        for section_match in severity_section.finditer(output):
            severity = section_match.group(1)
            section_text = section_match.group(2)

            for line_match in re.finditer(r"[-*]\s*(.+)", section_text):
                finding_id += 1
                description = line_match.group(1).strip()

                # Try to extract file:line from description
                file_match = re.search(r"([^\s:]+):(\d+)", description)
                if file_match:
                    file_path = file_match.group(1)
                    line_num = int(file_match.group(2))
                    # Remove file:line from description
                    description = re.sub(r"[^\s:]+:\d+\s*", "", description).strip()
                else:
                    file_path = "unknown"
                    line_num = 0

                findings.append(
                    Finding(
                        id=f"{agent_name}-{finding_id}",
                        file=file_path,
                        line=line_num,
                        category="general",
                        severity=parse_severity(severity),
                        confidence=50,
                        description=description,
                        evidence_refs=frozenset([agent_name]),
                        source_agent=agent_name,
                    )
                )

    return findings


def parse_json_findings(findings_json: List[Dict[str, Any]]) -> List[Finding]:
    """Parse findings from JSON format.

    Args:
        findings_json: List of finding dictionaries.

    Returns:
        List of Finding objects.
    """
    findings = []

    for i, f in enumerate(findings_json):
        try:
            source_agent = f.get("source_agent", "unknown")
            # Use source_agent as evidence_ref if not explicitly provided
            evidence_refs = f.get(
                "evidence_refs", [source_agent] if source_agent != "unknown" else []
            )
            finding = Finding(
                id=f.get("id", f"finding-{i + 1}"),
                file=f.get("file", "unknown"),
                line=f.get("line", 0),
                category=f.get("category", "general"),
                severity=parse_severity(f.get("severity", "low")),
                confidence=parse_confidence(f.get("confidence", 50)),
                description=f.get("description", ""),
                evidence_refs=frozenset(evidence_refs),
                source_agent=source_agent,
            )
            findings.append(finding)
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid finding: {e}")
            continue

    return findings


# =============================================================================
# FILTERING
# =============================================================================


def apply_filtering(
    findings: List[Finding],
    context: ProjectContext,
    evidence_mode: bool = False,
) -> Dict[str, Any]:
    """Apply 3-Layer Defense filtering to findings.

    Args:
        findings: List of Finding objects to filter.
        context: ProjectContext for filtering decisions.
        evidence_mode: Whether to run Layer 3 evidence validation.

    Returns:
        Dictionary with filtered results and statistics.
    """
    # Layer 2: Mechanical Filtering
    filter = FindingFilter(context)
    filtered_results = filter.filter_findings(findings)

    # Separate active and suppressed
    active = [r for r in filtered_results if not r.is_suppressed]
    suppressed = [r for r in filtered_results if r.is_suppressed]

    # Layer 3: Evidence-Based Validation (optional)
    if evidence_mode:
        validation = ValidationPass(context, ValidationMode.EVIDENCE)
        active_findings = [r.finding for r in active]
        validated_findings = validation.validate_findings(active_findings)

        # Update filtered results with validated findings
        active = []
        validated_idx = 0
        for result in filtered_results:
            if not result.is_suppressed:
                # Replace with validated finding
                validated = (
                    validated_findings[validated_idx]
                    if validated_idx < len(validated_findings)
                    else result.finding
                )
                validated_idx += 1
                # If validation set confidence to 0, suppress
                if validated.confidence == 0:
                    active.append(
                        FilteredFinding(
                            finding=validated,
                            action=FilterAction.SUPPRESS,
                            filtered_confidence=0,
                            reason=f"Validation pass: {result.reason}",
                        )
                    )
                else:
                    active.append(
                        FilteredFinding(
                            finding=validated,
                            action=result.action,
                            filtered_confidence=validated.confidence,
                            reason=result.reason,
                        )
                    )

    # Categorize by confidence
    categories = filter.categorize_findings([r.finding for r in active])

    # Add suppressed findings to categories
    categories["suppressed"] = [
        {"finding": r.finding, "reason": r.reason} for r in suppressed
    ]

    # Get summary statistics
    summary = filter.get_summary([r.finding for r in filtered_results])

    return {
        "categories": categories,
        "active": active,
        "suppressed": suppressed,
        "summary": summary,
        "filter_effectiveness": summary.get("filter_effectiveness", 0),
    }


def format_results(results: Dict[str, Any]) -> str:
    """Format filtered results as markdown.

    Args:
        results: Filtered results dictionary.

    Returns:
        Markdown-formatted string.
    """
    lines = ["# Code Review Summary (Filtered)\n"]

    categories = results["categories"]
    summary = results["summary"]

    # Summary stats
    lines.append("## Filter Statistics\n")
    lines.append(f"- **Total findings:** {summary.get('total_findings', 0)}")
    lines.append(f"- **Active findings:** {summary.get('active_findings', 0)}")
    lines.append(f"- **Suppressed:** {summary.get('suppressed_findings', 0)}")
    lines.append(
        f"- **Filter effectiveness:** {results.get('filter_effectiveness', 0):.1f}%\n"
    )

    # Critical Issues
    critical = categories.get("critical", [])
    if critical:
        lines.append(f"## Critical Issues ({len(critical)} found)\n")
        for ff in critical:
            f = ff.finding
            agent = list(f.evidence_refs)[0] if f.evidence_refs else "unknown"
            lines.append(
                f"- [{agent}]: {f.description} [{f.file}:{f.line}] (confidence: {ff.filtered_confidence})"
            )
        lines.append("")

    # Important Issues
    important = categories.get("important", [])
    if important:
        lines.append(f"## Important Issues ({len(important)} found)\n")
        for ff in important:
            f = ff.finding
            agent = list(f.evidence_refs)[0] if f.evidence_refs else "unknown"
            lines.append(
                f"- [{agent}]: {f.description} [{f.file}:{f.line}] (confidence: {ff.filtered_confidence})"
            )
        lines.append("")

    # Suggestions
    suggestions = categories.get("suggestions", [])
    if suggestions:
        lines.append(f"## Suggestions ({len(suggestions)} found)\n")
        for ff in suggestions:
            f = ff.finding
            agent = list(f.evidence_refs)[0] if f.evidence_refs else "unknown"
            lines.append(
                f"- [{agent}]: {f.description} [{f.file}:{f.line}] (confidence: {ff.filtered_confidence})"
            )
        lines.append("")

    # Suppressed
    suppressed = categories.get("suppressed", [])
    if suppressed:
        lines.append(f"## Suppressed Findings ({len(suppressed)} filtered)\n")
        lines.append("| Finding | Reason |")
        lines.append("|---------|--------|")
        for item in suppressed:
            finding = item["finding"]
            reason = item["reason"]
            lines.append(f"| {finding.description[:50]}... | {reason} |")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate and filter code review findings"
    )
    parser.add_argument(
        "--context-json", required=True, help="Path to ProjectContext JSON file"
    )
    parser.add_argument(
        "--findings-json", help="Path to findings JSON file (structured format)"
    )
    parser.add_argument(
        "--findings-dir", help="Directory containing agent output files"
    )
    parser.add_argument(
        "--evidence-mode",
        action="store_true",
        help="Enable Layer 3 evidence-based validation",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format",
    )

    args = parser.parse_args()

    # Load context
    try:
        with open(args.context_json, "r") as f:
            context_data = json.load(f)
        context = ProjectContext.from_dict(context_data)
    except Exception as e:
        print(f"Error loading context: {e}", file=sys.stderr)
        sys.exit(1)

    # Load findings
    findings: List[Finding] = []

    if args.findings_json:
        try:
            with open(args.findings_json, "r") as f:
                findings_data = json.load(f)
            findings.extend(parse_json_findings(findings_data))
        except Exception as e:
            print(f"Error loading findings JSON: {e}", file=sys.stderr)
            sys.exit(1)

    if args.findings_dir:
        findings_dir = Path(args.findings_dir)
        for output_file in findings_dir.glob("*.txt"):
            agent_name = output_file.stem
            try:
                output = output_file.read_text(encoding="utf-8")
                findings.extend(parse_agent_output(agent_name, output))
            except Exception as e:
                logger.warning(f"Error parsing {output_file}: {e}")

    if not findings:
        print("No findings to process", file=sys.stderr)
        sys.exit(0)

    logger.info(f"Loaded {len(findings)} findings")

    # Apply filtering
    results = apply_filtering(findings, context, args.evidence_mode)

    # Output results
    if args.output_format == "json":
        # Convert to JSON-serializable format
        output = {
            "summary": results["summary"],
            "categories": {
                k: [
                    {
                        "id": f.finding.id,
                        "file": f.finding.file,
                        "line": f.finding.line,
                        "severity": f.finding.severity,
                        "confidence": f.filtered_confidence,
                        "description": f.finding.description,
                        "source_agent": f.finding.source_agent,
                    }
                    for f in v
                ]
                if k != "suppressed"
                else [
                    {
                        "id": item["finding"].id,
                        "description": item["finding"].description,
                        "reason": item["reason"],
                    }
                    for item in v
                ]
                for k, v in results["categories"].items()
            },
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_results(results))


if __name__ == "__main__":
    main()
