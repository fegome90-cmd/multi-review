#!/usr/bin/env python3
"""
Gate checker for multi-review benchmark results.

This module provides gate checking functionality to validate that
benchmark results meet quality thresholds:
- FP rate < 15%
- Latency p95 < 500ms (cache hit)
- Cache hit rate > 80%
- Schema stability (snapshots match)

Exit codes:
- 0: All gates passed
- 1: One or more gates failed
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import ExitCodes from utils
from utils import ExitCodes

# Default gate thresholds
GATES = {
    "fp_rate_max": 0.15,  # FP rate < 15%
    "latency_p95_max_ms": 500,  # p95 < 500ms (cache hit)
    "cache_hit_rate_min": 0.80,  # Cache hit > 80%
    "schema_stability": True,  # Snapshots match
}

# Degradation policy for CI
DEGRADATION_POLICY = {
    "PARTIAL": "warn",  # Log warning, don't fail
    "DEGRADED": "warn",  # Log warning, don't fail
    "OFFLINE": "fail",  # Fail the gate
}


@dataclass
class GateResult:
    """Result of a gate check."""

    name: str
    passed: bool
    actual: Any
    threshold: Any
    message: str


def check_fp_rate(results: Dict[str, Any]) -> GateResult:
    """Check FP rate gate.

    Args:
        results: Benchmark results dictionary.

    Returns:
        GateResult with pass/fail status.
    """
    fp_rate = results.get("fp_rate", 0.0)
    threshold = GATES["fp_rate_max"]
    passed = fp_rate <= threshold

    return GateResult(
        name="fp_rate",
        passed=passed,
        actual=fp_rate,
        threshold=threshold,
        message=f"FP rate {fp_rate:.1%} {'<=' if passed else '>'} {threshold:.1%}",
    )


def check_latency(results: Dict[str, Any]) -> GateResult:
    """Check latency gate.

    Args:
        results: Benchmark results dictionary.

    Returns:
        GateResult with pass/fail status.
    """
    latency_p95 = results.get("latency_p95_ms", 0)
    threshold = GATES["latency_p95_max_ms"]
    passed = latency_p95 <= threshold

    return GateResult(
        name="latency_p95",
        passed=passed,
        actual=latency_p95,
        threshold=threshold,
        message=f"p95 latency {latency_p95}ms {'<=' if passed else '>'} {threshold}ms",
    )


def check_cache_hit_rate(results: Dict[str, Any]) -> GateResult:
    """Check cache hit rate gate.

    Args:
        results: Benchmark results dictionary.

    Returns:
        GateResult with pass/fail status.
    """
    cache_hit_rate = results.get("cache_hit_rate", 0.0)
    threshold = GATES["cache_hit_rate_min"]
    passed = cache_hit_rate >= threshold

    return GateResult(
        name="cache_hit_rate",
        passed=passed,
        actual=cache_hit_rate,
        threshold=threshold,
        message=f"Cache hit rate {cache_hit_rate:.1%} {'>=' if passed else '<'} {threshold:.1%}",
    )


def check_schema_stability(results: Dict[str, Any]) -> GateResult:
    """Check schema stability gate.

    Args:
        results: Benchmark results dictionary.

    Returns:
        GateResult with pass/fail status.
    """
    schema_stable = results.get("schema_stable", True)
    passed = schema_stable == GATES["schema_stability"]

    return GateResult(
        name="schema_stability",
        passed=passed,
        actual=schema_stable,
        threshold=GATES["schema_stability"],
        message=f"Schema stability {'passed' if passed else 'failed'}",
    )


def check_all_gates(results: Dict[str, Any]) -> Tuple[bool, List[GateResult]]:
    """Check all gates against benchmark results.

    Args:
        results: Benchmark results dictionary.

    Returns:
        Tuple of (all_passed, list of GateResult).
    """
    gate_checks = [
        check_fp_rate(results),
        check_latency(results),
        check_cache_hit_rate(results),
        check_schema_stability(results),
    ]

    all_passed = all(g.passed for g in gate_checks)
    return all_passed, gate_checks


def load_results(results_path: Path) -> Dict[str, Any]:
    """Load benchmark results from JSON file.

    Args:
        results_path: Path to results JSON file.

    Returns:
        Dictionary with benchmark results.

    Raises:
        FileNotFoundError: If the results file does not exist.
        json.JSONDecodeError: If the results file contains invalid JSON.
    """
    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")

    content = results_path.read_text(encoding="utf-8")
    return json.loads(content)


def print_report(
    results: Dict[str, Any], gate_results: List[GateResult], all_passed: bool
) -> None:
    """Print gate check report.

    Args:
        results: Benchmark results dictionary.
        gate_results: List of gate check results.
        all_passed: Whether all gates passed.
    """
    print("=" * 60)
    print("GATE CHECK REPORT")
    print("=" * 60)
    print()

    # Print summary
    print("Summary:")
    print(f"  Total findings: {results.get('total_findings', 0)}")
    print(f"  FP rate: {results.get('fp_rate', 0.0):.1%}")
    print(f"  Latency p50: {results.get('latency_p50_ms', 0)}ms")
    print(f"  Latency p95: {results.get('latency_p95_ms', 0)}ms")
    print(f"  Cache hit rate: {results.get('cache_hit_rate', 0.0):.1%}")
    print()

    # Print gate results
    print("Gates:")
    for gate in gate_results:
        status = "✓ PASS" if gate.passed else "✗ FAIL"
        print(f"  [{status}] {gate.name}: {gate.message}")
    print()

    # Print final result
    print("=" * 60)
    if all_passed:
        print("RESULT: ALL GATES PASSED")
    else:
        failures = [g for g in gate_results if not g.passed]
        print(f"RESULT: {len(failures)} GATE(S) FAILED")
        for gate in failures:
            print(f"  - {gate.name}: {gate.message}")
    print("=" * 60)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code from ExitCodes enum.
    """
    try:
        import argparse

        parser = argparse.ArgumentParser(description="Check benchmark gates")
        parser.add_argument(
            "results_file",
            type=Path,
            help="Path to benchmark results JSON file",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output results as JSON",
        )
        parser.add_argument(
            "--fp-rate-max",
            type=float,
            default=GATES["fp_rate_max"],
            help=f"Maximum FP rate (default: {GATES['fp_rate_max']})",
        )
        parser.add_argument(
            "--latency-p95-max",
            type=int,
            default=GATES["latency_p95_max_ms"],
            help=f"Maximum p95 latency in ms (default: {GATES['latency_p95_max_ms']})",
        )
        parser.add_argument(
            "--cache-hit-rate-min",
            type=float,
            default=GATES["cache_hit_rate_min"],
            help=f"Minimum cache hit rate (default: {GATES['cache_hit_rate_min']})",
        )

        args = parser.parse_args()

        # Update gates with CLI args
        GATES["fp_rate_max"] = args.fp_rate_max
        GATES["latency_p95_max_ms"] = args.latency_p95_max
        GATES["cache_hit_rate_min"] = args.cache_hit_rate_min

        # Load results (may raise FileNotFoundError, json.JSONDecodeError)
        results = load_results(args.results_file)

        # Check all gates
        all_passed, gate_results = check_all_gates(results)

        # Output report
        if args.json:
            output = {
                "passed": all_passed,
                "gates": [
                    {
                        "name": g.name,
                        "passed": g.passed,
                        "actual": g.actual,
                        "threshold": g.threshold,
                        "message": g.message,
                    }
                    for g in gate_results
                ],
                "summary": {
                    "total_findings": results.get("total_findings", 0),
                    "fp_rate": results.get("fp_rate", 0.0),
                    "latency_p50_ms": results.get("latency_p50_ms", 0),
                    "latency_p95_ms": results.get("latency_p95_ms", 0),
                    "cache_hit_rate": results.get("cache_hit_rate", 0.0),
                },
            }
            print(json.dumps(output, indent=2))
        else:
            print_report(results, gate_results, all_passed)

        return ExitCodes.SUCCESS if all_passed else ExitCodes.FAILURE

    except SystemExit as e:
        # Handle argparse-generated exits (e.g., --help)
        return ExitCodes.INVALID_ARGS
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return ExitCodes.CONFIG_ERROR
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error: Invalid JSON in results file: {e}", file=sys.stderr)
        return ExitCodes.CONFIG_ERROR
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return ExitCodes.FAILURE


if __name__ == "__main__":
    sys.exit(main())
