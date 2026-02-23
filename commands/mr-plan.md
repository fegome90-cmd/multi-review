---
description: Evaluate implementation plans with multi-agent analysis
argument-hint: [--file PATH | --plan-text "text"] [--preset=quick|thorough|comprehensive] [--workflow=feature|bugfix|refactor|security]
allowed-tools: ["Task", "AskUserQuestion"]
---

# /mr-plan

Invoke the **mr-plan-evaluator** agent to analyze implementation plans.

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `--file` | - | Plan file path (YAML/Markdown) - RELATIVE to workspace |
| `--plan-text` | - | Plan description as text |
| `--preset` | thorough | Evaluation depth: quick (2), thorough (4), comprehensive (7) |
| `--workflow` | feature | Plan type: feature, bugfix, refactor, security |

## Instructions

### Step 1: Input Validation (Zero-Trust)

**BEFORE invoking agent, validate file path if `--file` is provided:**

```
IF --file is provided:
    path = value of --file

    # Path Traversal Check
    IF path contains "..":
        STOP and show error: "Path traversal detected. Use relative path without .."
        DO NOT proceed

    IF path starts with "/" OR path starts with "~":
        STOP and show error: "Absolute paths not allowed. Use relative path from workspace root."
        DO NOT proceed

    # Sensitive Directory Check
    IF path contains ".claude/" OR path contains ".env" OR path contains ".ssh/" OR path contains ".git/":
        STOP and show error: "Access denied: Cannot access sensitive directories"
        DO NOT proceed

    # Valid path - proceed to Step 2
```

### Step 1.5: Pre-flight Check

**BEFORE invoking agent:**
1. Verify multi-review plugin is installed
2. Verify mr-plan-evaluator agent is available
3. IF either missing:
   STOP with error: "❌ **Error:** mr-plan-evaluator not found.
   Install with: /plugin install multi-review@local"

### Step 2: Invoke Agent

Invoke the mr-plan-evaluator agent with the validated context:

```
Task: multi-review:mr-plan-evaluator

Context to pass:
- file: {validated --file value or null}
- plan_text: {--plan-text value or null}
- preset: {--preset value, default: thorough}
- workflow: {--workflow value, default: feature}
```

### Step 3: Delegate to Agent

**DO NOT:**
- ❌ Evaluate the plan yourself
- ❌ Write or modify any files
- ❌ Execute shell commands
- ❌ Read files directly (let agent handle)
- ❌ Bypass the agent

**The agent handles:**
1. Loading and sanitizing plan content
2. Dispatching appropriate subagents based on preset
3. Aggregating findings into structured report
4. Presenting evaluation with recommendations
5. Offering next steps

**Your only job:**
1. Validate input (Step 1)
2. Invoke agent (Step 2)
3. Let the agent do the work

### Step 4: Handle Agent Response

**IF agent response contains "Error:" or is empty:**
1. Report: "❌ **Agent Error:** {error_message}"
2. Suggest: "Run /mr-doctor to diagnose plugin issues"

**IF agent response indicates incomplete analysis:**
1. Report: "⚠️ **Partial Results:** {reason}"
2. Offer: "Retry?" or "View partial results?"

---

## Presets

See `resources/preset-definitions.md` for agent assignments.

| Preset | Time |
|--------|------|
| quick | ~30s |
| thorough | ~2min |
| comprehensive | ~5min |

**Default:** thorough

---

## Workflow Types

| Workflow | Focus Adjustment |
|----------|-----------------|
| `feature` | Balanced evaluation |
| `bugfix` | Risk-focused, regression check |
| `refactor` | Simplification-focused |
| `security` | Always includes security-reviewer |

---

## Usage

```bash
# Evaluate a plan file (thorough preset)
/mr-plan --file _ctx/plans/PLAN-2026-0001/plan-tree.yaml

# Quick evaluation
/mr-plan --file docs/plans/feature.md --preset quick

# From text description
/mr-plan --plan-text "Implement OAuth with Google and GitHub"

# Comprehensive security evaluation
/mr-plan --file security-plan.yaml --preset comprehensive --workflow security

# Interactive (no args - agent will ask)
/mr-plan
```

---

## Security

This command enforces:
- ✅ Path traversal prevention (no `..` in paths)
- ✅ No absolute paths (must be relative to workspace)
- ✅ Sensitive directory protection (.claude/, .env/, .ssh/, .git/)
- ✅ Minimal tool access (Task + AskUserQuestion only)

The agent additionally enforces:
- ✅ Prompt injection detection and sanitization
- ✅ JSON schema validation for subagent outputs
- ✅ Read-only operation (no Write, Edit, Bash)

---

## When to Use

- Before executing a complex plan
- After creating a plan with /plan-orch
- When reviewing someone else's plan
- Before PRs with significant changes
- To identify simplification opportunities

## When NOT to Use

- Simple, obvious changes
- Plans you've already evaluated
- Quick iterations (use /mr-quick on code instead)

---

## See Also

**Plan Creation:**
- `/plan-orch` - Create enterprise plans (enterprise-planning plugin)

**Code Review:**
- `/mr-quick` - 2-agent fast review
- `/mr-thorough` - 4-agent balanced review
- `/mr-comprehensive` - 7-agent complete review
- `/multi-review` - Interactive review selection

**Diagnostics:**
- `/mr-doctor` - Plugin diagnostics
