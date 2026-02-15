---
description: Plan and execute features with multi-agent orchestration
allowed-tools: Skill, Task, TaskOutput, AskUserQuestion, Bash, Read, Write, Edit
---

# Multi-Agent Planning & Execution (mr-plan)

Plan and implement features using the everything-claude-code orchestration workflow.

## Variables

- `--workflow`: Workflow type (feature|bugfix|refactor|security). Default: feature
- `--skip-verification`: Skip final verification loop

## Instructions

This command orchestrates planning and execution using everything-claude-code skills, optimized for GLM-5's rate limits (~60 RPM).

### Workflow Overview

```
plan → orchestrate → [optional] verification-loop
```

**API Efficiency:** 4-5 agent calls total (vs 30+ with superpowers approach)

### Step 1: Requirements Gathering

Ask the user to describe what they want to build:

```
What feature or change would you like to plan and implement?
```

Wait for their response before proceeding.

### Step 2: Invoke Planning Skill

```bash
# This creates a detailed implementation plan
/everything-claude-code:plan
```

The planner agent will:
1. Restate requirements in clear terms
2. Identify risks and blockers
3. Break down into implementation phases
4. Wait for user confirmation

**IMPORTANT:** Do NOT proceed to Step 3 until the user explicitly approves the plan.

### Step 3: Execute with Orchestration

Once the plan is approved:

```bash
# Execute the plan with TDD workflow
/everything-claude-code:orchestrate
```

The orchestrate skill will:
1. Run tdd-guide agent for implementation
2. Run code-reviewer agent for quality check
3. Optionally run security-reviewer (parallel)

### Step 4: Verification Loop (Optional)

For complex features, run additional verification:

```bash
# 6-phase verification if --skip-verification is NOT set
/everything-claude-code:verification-loop
```

Verification phases:
1. Type checking
2. Linting
3. Unit tests
4. Integration tests
5. Build verification
6. Manual checklist

### Step 5: Summary and Next Steps

Present a summary of what was completed:

```markdown
## Implementation Complete

**Workflow:** {workflow_type}
**Phases Completed:**
- [x] Planning
- [x] Orchestration
- [x] Verification (if applicable)

**Files Modified:** {count} files
**Tests Added:** {count} tests

### Next Steps
- Run `/mr-quick` to review the changes
- Commit with `/commit` when ready
- Or continue with additional changes
```

## Workflow Types

| Type | Description | Agents Used |
|------|-------------|-------------|
| `feature` | New feature development | planner → tdd-guide → code-reviewer |
| `bugfix` | Bug fixes | planner → tdd-guide → code-reviewer |
| `refactor` | Code refactoring | planner → tdd-guide → code-reviewer |
| `security` | Security-focused changes | planner → tdd-guide → security-reviewer |

## Usage Examples

```bash
# Plan and implement a new feature (interactive)
/mr-plan

# Bug fix workflow
/mr-plan --workflow bugfix

# Security-focused changes
/mr-plan --workflow security

# Skip verification for faster iteration
/mr-plan --skip-verification
```

## Rate Limit Considerations

This workflow is optimized for GLM-5's ~60 RPM limit:

| Phase | API Calls | Cumulative |
|-------|-----------|------------|
| Planning | 1 | 1 |
| Orchestration | 2-3 | 3-4 |
| Verification | 1-2 | 4-6 |

**Total:** 4-6 calls over several minutes (well under 60 RPM)

## When to Use

- Starting a new feature
- Complex refactoring
- Security-sensitive changes
- Multi-file modifications
- When you need structured planning before coding

## When NOT to Use

- Single-file quick fixes → use direct editing
- Simple typos or config changes
- When you already have a clear plan

## See Also

- `/mr-quick` - 2-agent fast review
- `/mr-thorough` - 4-agent balanced review
- `/mr-comprehensive` - 7-agent complete review
- `/mr-doctor` - Plugin diagnostics
