---
description: Comprehensive 7-agent code review - full review before PRs
argument-hint: [--evidence-mode]
allowed-tools: Skill, Task, TaskOutput, AskUserQuestion, Bash, Read
---

# Comprehensive Review (mr-comprehensive)

Run a complete 7-agent code review for thorough analysis before important PRs.

## Variables

- `--evidence-mode`: Enable evidence-based validation (runs ruff/mypy for Layer 3)

## Instructions

This command runs the full review suite without the preset questionnaire.

### Agent Configuration

**Preset: comprehensive** (7 agents, ~5 minutes)

| Agent | Purpose |
|-------|---------|
| `feature-dev:code-reviewer` | General code review with confidence scoring |
| `pr-review-toolkit:code-reviewer` | Project guidelines compliance |
| `pr-review-toolkit:pr-test-analyzer` | Test coverage quality and completeness |
| `pr-review-toolkit:silent-failure-hunter` | Error handling and silent failures |
| `pr-review-toolkit:type-design-analyzer` | Type design quality and invariants |
| `pr-review-toolkit:comment-analyzer` | Code comment accuracy and maintainability |
| `pr-review-toolkit:code-simplifier` | Refactoring and simplification suggestions |

### Execution Workflow

**Step 1: Build project context (3-Layer Defense - Layer 1)**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/context_detector.py" --context-json
```

This extracts:
- **Python config**: mypy strictness, ruff rules, type checking level
- **Shell config**: Scripts with `set -euo pipefail` (strict mode)
- **Test config**: Test framework, coverage settings
- **Git metadata**: Changed files, branch info

Pass this context to each agent prompt to enable context-aware filtering.

**Step 2: Launch agents in parallel**

For EACH agent, launch a background agent:

```markdown
Task(
  subagent_type="<agent_type>",
  description="Code review: <agent_name>",
  prompt="<CALIBRATED_PROMPT_FROM_CACHE>

PROJECT CONTEXT:
- Python type checking: <mypy_strictness>
- Shell strict mode files: <strict_mode_files>
- Test framework: <test_framework>

Review the code changes in this workspace. Return findings with:
- Severity (critical/important/suggestion)
- Confidence score (0-100 based on criteria)
- File path and line numbers
- Brief description
- Suggested fix (if applicable)",
  run_in_background=true
)
```

Store the returned `task_id` for each agent.

**Step 3: Wait for all agents to complete**

Use `TaskOutput(task_id=..., block=true, timeout=300000)` for each agent. Handle timeouts gracefully.

**Step 4: Filter and aggregate results (3-Layer Defense - Layers 2 & 3)**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/context_detector.py" --context-json > /tmp/project_context.json
```

Then aggregate findings:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/finding_aggregator.py" \
  --context-json /tmp/project_context.json \
  --findings-json /tmp/findings.json \
  ${EVIDENCE_MODE:+--evidence-mode} \
  --output-format markdown
```

**Confidence Scoring Criteria:**

| Score | Confidence | Description |
|-------|------------|-------------|
| 0 | False positive | Pre-existing issue or doesn't stand up to scrutiny |
| 25 | Low | Might be real, but couldn't verify - likely nitpick |
| 50 | Medium | Verified real issue, but nitpick or rarely hit |
| 75 | High | Very likely real issue that will be hit in practice |
| 100 | Certain | Definitely real, frequently hit, directly confirmed |

**Categorize findings:**
- **Critical Issues** (filtered_confidence: 75-100)
- **Important Issues** (filtered_confidence: 50-74)
- **Suggestions** (filtered_confidence: 25-49)
- **Suppressed** (with reason logged)
- **Strengths** (positive findings)

**Step 5: Present findings**

Display categorized findings with agent attribution and confidence scores. Include suppression reasons for traceability.

**Step 6: Collect feedback (optional learning)**

After displaying findings, offer to collect feedback for learning:

```markdown
AskUserQuestion({
  questions: [{
    question: "Would you like to provide feedback on these findings to improve future reviews?",
    header: "Feedback",
    multiSelect: false,
    options: [
      { label: "Yes, review findings", description: "Collect feedback on each finding" },
      { label: "No, skip feedback", description: "Continue without feedback collection" }
    ]
  }]
})
```

**Step 7: Ask for next action**

Use `AskUserQuestion` to offer:
- `Apply fixes` - Run `superpowers:receiving-code-review` to process feedback
- `Plan fixes` - Run `superpowers:brainstorming` to plan implementation
- `Debug issues` - Run `superpowers:systematic-debugging` if critical problems found
- `Stop` - End command (manual fixes later)

## Usage Examples

```bash
# Comprehensive review before important PR
/mr-comprehensive

# With evidence validation (recommended for comprehensive)
/mr-comprehensive --evidence-mode
```

## When to Use

- Before critical PRs
- Large refactoring changes
- Code affecting security or core functionality
- Final review before merging to main

## Output Format

```
# Code Review Summary

## Critical Issues (N found)
- [agent]: Description [file:line] (confidence: XX)
- ...

## Important Issues (N found)
- [agent]: Description [file:line] (confidence: XX)
- ...

## Suggestions (N found)
- [agent]: Description [file:line] (confidence: XX)
- ...

## Suppressed (N filtered)
- [agent]: Description - Reason: <suppression_reason>

## Strengths
- Positive findings about code quality
```

## See Also

- `/multi-review` - Full interactive review with preset selection
- `/mr-quick` - 2-agent fast review
- `/mr-thorough` - 4-agent balanced review
