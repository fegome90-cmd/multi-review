---
description: Quick 2-agent code review - fast check before commits
argument-hint: [--evidence-mode]
allowed-tools: Skill, Task, TaskOutput, AskUserQuestion, Bash, Read
---

# Quick Review (mr-quick)

Run a fast 2-agent code review optimized for quick checks before commits.

## Variables

- `--evidence-mode`: Enable evidence-based validation (runs ruff/mypy for Layer 3)

## Instructions

This command runs a streamlined review without the preset questionnaire.

### Agent Configuration

**Preset: quick** (2 agents, ~30 seconds)

| Agent | Purpose |
|-------|---------|
| `feature-dev:code-reviewer` | General code review with confidence scoring |
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

Use `TaskOutput(task_id=..., block=true, timeout=300000)` for each agent.

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

**Step 5: Present findings**

Display categorized findings with agent attribution and confidence scores.

**Step 6: Ask for next action**

Use `AskUserQuestion` to offer:
- `Apply fixes` - Run `superpowers:receiving-code-review` to process feedback
- `Plan fixes` - Run `superpowers:brainstorming` to plan implementation
- `Stop` - End command (manual fixes later)

## Usage Examples

```bash
# Quick check before committing
/mr-quick

# With evidence validation (slower but more accurate)
/mr-quick --evidence-mode
```

## When to Use

- Before committing small changes
- Quick sanity check on refactoring
- Pre-PR fast review
- When time is limited

## See Also

- `/multi-review` - Full interactive review with preset selection
- `/mr-thorough` - 4-agent balanced review
- `/mr-comprehensive` - 7-agent complete review
