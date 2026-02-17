# Suppression Reason Codes

This document describes the canonical reason codes used in the multi-review filtering system.

## Code Structure

Reason codes are namespaced by layer:
- **L2_***: Layer 2 (Mechanical Filtering) - Pattern-based rules
- **L3_***: Layer 3 (Evidence-Based Validation) - Tool verification rules

## Layer 2: Mechanical Filtering

These codes represent pattern-based filtering rules that don't require tool execution.

| Enum | Code Value | Rule ID | Description | Example |
|------|------------|---------|-------------|---------|
| `L2_SHELL_STRICT_MODE` | `L2_shell_strict_mode` | `L2_rule_shell_strict` | Shell script has `set -euo pipefail` | Exit code handling in strict shell |
| `L2_STYLE_NITPICK` | `L2_style_nitpick` | `L2_rule_style` | Non-actionable style issue | Variable naming, whitespace |
| `L2_INTERNAL_HELPER` | `L2_internal_helper` | `L2_rule_internal` | Internal helper function, mypy not strict | Private function missing type hints |
| `L2_MYPY_NOT_STRICT` | `L2_mypy_not_strict` | `L2_rule_mypy_relaxed` | Mypy configured as relaxed | Missing annotations in non-strict project |
| `L2_LOW_VALUE` | `L2_low_value` | `L2_rule_low_value` | Low confidence AND low severity | Minor suggestion with 20% confidence |
| `L2_TOOL_ALREADY_CATCHES` | `L2_tool_already_catches` | `L2_rule_tool_catches` | Existing tool already catches this | Ruff would flag this lint issue |
| `L2_OPTIONAL_ENHANCEMENT` | `L2_optional_enhancement` | `L2_rule_optional` | Optional enhancement suggestion | "Could consider" type feedback |
| `L2_PRE_EXISTING_CODE` | `L2_pre_existing_code` | `L2_rule_pre_existing` | Pre-existing code not changed in PR | Legacy code issues |
| `L2_LEARNED_PATTERN` | `L2_learned_pattern` | `L2_rule_learned_*` | Pattern learned from feedback | Previously marked as FP |

## Layer 3: Evidence-Based Validation

These codes represent findings suppressed or modified based on actual tool output.

| Enum | Code Value | Description | Example |
|------|------------|-------------|---------|
| `L3_NO_EVIDENCE_MATCH` | `L3_no_evidence_match` | No tool evidence supports finding | Agent claims error but tool doesn't |
| `L3_VALIDATION_CONTRADICTED` | `L3_validation_contradicted` | Tool output contradicts finding | Agent says bug, tests pass |
| `L3_TOOL_TIMEOUT` | `L3_tool_timeout` | Tool timed out during validation | Mypy took too long |
| `L3_TOOL_MISSING` | `L3_tool_missing` | Tool not installed or available | ruff not found |

## Usage in Code

### Creating Filter Rules

```python
from finding_filter import FilterRule, FilterAction, SuppressionReasonCode

rule: FilterRule = (
    is_shell_strict_mode,                    # Predicate
    FilterAction.SUPPRESS,                   # Action
    "Shell strict mode handles this",        # Human reason
    None,                                    # Confidence value (None for SUPPRESS)
    SuppressionReasonCode.L2_SHELL_STRICT_MODE,  # Reason code
    "L2_rule_shell_strict",                  # Rule ID
)
```

### Checking Reason Codes in Tests

```python
def test_shell_strict_mode_has_reason_code():
    filtered = filter.filter_finding(finding)
    assert filtered.reason_code == SuppressionReasonCode.L2_SHELL_STRICT_MODE
    assert filtered.filter_rule_id == "L2_rule_shell_strict"
```

## Adding New Reason Codes

1. Add the code to `SuppressionReasonCode` enum in `finding_filter.py`
2. Document it in this file with description and example
3. Create or update the filter rule with the new code
4. Add a test verifying the code is set correctly

## Metrics and Monitoring

Reason codes enable:
- **FP rate tracking**: Count suppressions by reason code
- **Rule effectiveness**: Which rules suppress the most findings
- **Calibration**: Adjust thresholds per rule based on feedback
