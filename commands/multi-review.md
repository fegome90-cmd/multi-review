---
description: Interactive multi-agent code review with smart agent selection and false positive elimination
argument-hint: [--agents AGENTS] [--evidence-mode] [--refresh-cache]
allowed-tools: Skill, Task, TaskOutput, AskUserQuestion, Bash, Read
---

# Multi-Agent Code Review

Run comprehensive code reviews using multiple specialized agents with interactive configuration and false positive elimination via 3-Layer Defense.

## Variables

- `--agents AGENTS`: Comma-separated agent list or preset name (optional, prompts if not provided)
- `--evidence-mode`: Enable evidence-based validation (runs ruff/mypy for Layer 3)
- `--refresh-cache`: Refresh DSPy prompt cache (takes 30+ seconds, user-initiated only)

## Instructions

This command orchestrates multiple code review agents. When invoked, follow this exact workflow:

### Execution Workflow

**Step 1: Detect context (optional)**
Run the Python script to get context-aware suggestions:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/context_detector.py" --suggest
```
Use this to inform the default preset choice, but don't auto-select without user confirmation.

**Step 1.5: Build project context (3-Layer Defense - Layer 1)**

Before launching agents, build the ProjectContext for false positive elimination:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/context_detector.py" --context-json
```

This extracts:
- **Python config**: mypy strictness, ruff rules, type checking level
- **Shell config**: Scripts with `set -euo pipefail` (strict mode)
- **Test config**: Test framework, coverage settings
- **Git metadata**: Changed files, branch info

Pass this context to each agent prompt to enable context-aware filtering.

**Step 2: Determine agents to run**

If `--agents` argument is provided:
- Parse the comma-separated list OR use the preset name directly
- Validate that all specified agents exist (try-catch with informative error)
- Skip to Step 3

If NO `--agents` argument:
- Use `AskUserQuestion` to let the user choose a preset:
  - `quick` - 2 agents (fast check)
  - `thorough` - 4 agents (balanced)
  - `comprehensive` - 7 agents (complete)
  - `custom` - Interactive multi-select of individual agents
  - `framework` - Framework-specific guidance

**Step 3: Launch agents in parallel**

For EACH agent in the selected preset, launch a background agent using the Task tool.

**CRITICAL:** Use calibrated prompts from DSPy cache (Layer 1). The prompt includes project context:

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

**Calibrated prompts are loaded from cache (~1ms) - NEVER wait for API.**

Store the returned `task_id` for each agent in a list for later retrieval.

**Agent mappings for presets:**

| Preset | Agents to Launch |
|--------|------------------|
| `quick` | 2 agents: `feature-dev:code-reviewer` (general) + `pr-review-toolkit:code-simplifier` (refactoring) |
| `thorough` | 4 agents: `feature-dev:code-reviewer`, `pr-review-toolkit:pr-test-analyzer`, `pr-review-toolkit:silent-failure-hunter`, `pr-review-toolkit:code-simplifier` |
| `comprehensive` | All 7 agents: `feature-dev:code-reviewer`, `pr-review-toolkit:code-reviewer`, `pr-review-toolkit:pr-test-analyzer`, `pr-review-toolkit:silent-failure-hunter`, `pr-review-toolkit:type-design-analyzer`, `pr-review-toolkit:comment-analyzer`, `pr-review-toolkit:code-simplifier` |
| `framework` | 2 agents: `superpowers:code-review-checklist`, `pr-review-toolkit:code-simplifier` |

### Confidence Scoring Criteria

| Score | Confidence | Description |
|-------|------------|-------------|
| 0 | False positive | Pre-existing issue or doesn't stand up to scrutiny |
| 25 | Low | Might be real, but couldn't verify - likely nitpick |
| 50 | Medium | Verified real issue, but nitpick or rarely hit |
| 75 | High | Very likely real issue that will be hit in practice |
| 100 | Certain | Definitely real, frequently hit, directly confirmed |

**Step 4: Wait for all agents to complete**

Use `TaskOutput(task_id=..., block=true, timeout=300000)` for each agent to retrieve results. Handle timeouts gracefully and report which agents didn't complete.

**Step 5: Filter and aggregate results (3-Layer Defense - Layers 2 & 3)**

First, save the context JSON:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/context_detector.py" --context-json > /tmp/project_context.json
```

Then parse all agent outputs and apply filtering using the aggregator:
```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/finding_aggregator.py" \
  --context-json /tmp/project_context.json \
  --findings-json /tmp/findings.json \
  ${EVIDENCE_MODE:+--evidence-mode} \
  --output-format markdown
```

The aggregator applies 3-Layer Defense filtering:
- **Layer 2 (Mechanical Filtering)**: Typed predicates suppress known false positives
- **Layer 3 (Evidence Validation)**: Optional cross-reference with ruff/mypy (when `--evidence-mode`)

**Categorize findings by filtered confidence:**
- **Critical Issues** (filtered_confidence: 75-100)
- **Important Issues** (filtered_confidence: 50-74)
- **Suggestions** (filtered_confidence: 25-49)
- **Suppressed** (with reason logged)
- **Strengths** (positive findings)

**Suppression Reasons (Layer 2):**
| Reason | Description |
|--------|-------------|
| Shell strict mode | `set -euo pipefail` handles error handling |
| Style nitpick | Low-severity formatting/naming issues |
| Internal helper | Type annotations not required for `_` prefixed functions |
| Low value | Low confidence + low severity |
| Tool already catches | ruff/mypy would flag this |

Include which agent found each issue and suppression reason for traceability.

**Step 6: Ask for next action**

Use `AskUserQuestion` to offer:
- `Apply fixes` - Run `superpowers:receiving-code-review` to process feedback
- `Plan fixes` - Run `superpowers:brainstorming` to plan implementation
- `Debug issues` - Run `superpowers:systematic-debugging` if critical problems found
- `Stop` - End command (manual fixes later)

### Available Agents

**Primary (Recommended):**
- `feature-dev:code-reviewer` - General code review with confidence scoring

**Specialized (pr-review-toolkit):**
- `pr-review-toolkit:code-reviewer` - Project guidelines review
- `pr-review-toolkit:pr-test-analyzer` - Test coverage quality and completeness
- `pr-review-toolkit:silent-failure-hunter` - Error handling and silent failures
- `pr-review-toolkit:type-design-analyzer` - Type design quality and invariants
- `pr-review-toolkit:comment-analyzer` - Code comment accuracy and maintainability
- `pr-review-toolkit:code-simplifier` - Code simplification and refactoring

**Framework-Specific:**
- `superpowers:code-review-checklist` - Framework-specific review guidance

### Presets

- `quick` - 2 agents: `feature-dev:code-reviewer` (general) + `pr-review-toolkit:code-simplifier` (refactoring)
- `thorough` - 4 agents: general review + tests + error handling + simplification
- `comprehensive` - All 7 agents (feature-dev + all pr-review-toolkit agents)
- `framework` - 2 agents: `superpowers:code-review-checklist` + `pr-review-toolkit:code-simplifier` (framework-specific + refactoring)
- `custom` - Select agents individually for maximum flexibility

### Custom Agent Selection

When the user selects `custom` preset, use `AskUserQuestion` with multi-select enabled and default selections:

```markdown
AskUserQuestion({
  questions: [{
    question: "Which agents would you like to run for code review?",
    header: "Agent Selection",
    multiSelect: true,
    options: [
      { label: "General Review", description: "feature-dev:code-reviewer - Broad code review with confidence scoring" },
      { label: "Guidelines Check", description: "pr-review-toolkit:code-reviewer - Project guidelines compliance" },
      { label: "Test Coverage", description: "pr-review-toolkit:pr-test-analyzer - Test quality and completeness" },
      { label: "Error Handling", description: "pr-review-toolkit:silent-failure-hunter - Silent failures detection" },
      { label: "Type Design", description: "pr-review-toolkit:type-design-analyzer - Type system quality" },
      { label: "Comments", description: "pr-review-toolkit:comment-analyzer - Documentation accuracy" },
      { label: "Code Simplifier", description: "pr-review-toolkit:code-simplifier - Refactoring suggestions" }
    ],
    default: ["General Review", "Test Coverage"]
  }]
})
```

Validate that at least one agent is selected before proceeding.

Then launch only the selected agents using the Task tool in Step 3.

## Workflow Examples

```bash
# Interactive mode (prompts for preset selection)
/multi-review

# Quick check - 2 agents
/multi-review --agents quick

# Thorough review - 4 agents in parallel
/multi-review --agents thorough

# Comprehensive review - all 7 agents in parallel
/multi-review --agents comprehensive

# Framework-specific review
/multi-review --agents framework

# Custom agent selection (interactive multi-select)
/multi-review --agents custom

# Direct agent list (custom selection without prompt)
/multi-review --agents feature-dev:code-reviewer,pr-review-toolkit:pr-test-analyzer,pr-review-toolkit:type-design-analyzer

# Evidence-based validation (runs ruff/mypy to verify findings)
/multi-review --agents thorough --evidence-mode

# Refresh prompt calibration (takes 30+ seconds)
/multi-review --refresh-cache
```

**Note:** When agents are specified, they launch in parallel using background Task tool. The command waits for all to complete before aggregating results.

## Smart Context Detection

The command automatically detects:

- **Git state**: Working directory, staged changes, or active PR
- **File types**: Tests, type definitions, documentation, code
- **Change size**: Line count to determine review depth

**Suggested agents based on context:**

| Context | Suggestion |
|---------|------------|
| Small change (<50 lines) | `feature-dev:code-reviewer` only |
| PR with tests | `feature-dev:code-reviewer` + `pr-review-toolkit:pr-test-analyzer` |
| Has test files | `feature-dev:code-reviewer` + `pr-review-toolkit:pr-test-analyzer` |
| Has type definitions | `feature-dev:code-reviewer` + `pr-review-toolkit:type-design-analyzer` |
| Large change (>500 lines) | `comprehensive` preset |

## Output Formats

### Markdown Summary (default)
Human-readable summary with categorized findings:
```
# Code Review Summary

## Critical Issues (2 found)
- [feature-dev:code-reviewer]: Null pointer risk [src/auth.ts:42] (confidence: 85)
- [pr-review-toolkit:silent-failure-hunter]: Missing error handling [src/api.py:128] (confidence: 78)

## Important Issues (5 found)
- [pr-review-toolkit:pr-test-analyzer]: Missing edge case test [tests/user.test.ts:45] (confidence: 65)
- ...

## Suggestions (3 found)
- [pr-review-toolkit:code-simplifier]: Can extract to function [src/utils.ts:112] (confidence: 45)

## Strengths
- Excellent type safety throughout
- Comprehensive test coverage (92%)
```

### Detailed Report
Full agent outputs with line-by-line analysis

### JSON
Structured format for programmatic processing:
```json
{
  "summary": {"critical": 2, "important": 5, "suggestions": 3, "strengths": 2},
  "findings": [
    {
      "agent": "feature-dev:code-reviewer",
      "severity": "critical",
      "confidence": 85,
      "file": "src/auth.ts",
      "line": 42,
      "description": "Null pointer risk when user is undefined",
      "suggested_fix": "Add null check before accessing user.id"
    },
    {
      "agent": "pr-review-toolkit:silent-failure-hunter",
      "severity": "critical",
      "confidence": 78,
      "file": "src/api.py",
      "line": 128,
      "description": "Missing error handling for network request",
      "suggested_fix": "Wrap request in try-catch and handle timeout"
    }
  ]
}
```

## Post-Review Actions

After review completes, choose next step:

1. **Continue with fixes** - Invokes `superpowers:receiving-code-review` to process feedback with technical rigor
2. **Plan fixes** - Invokes `superpowers:brainstorming` to plan implementation
3. **Debug issues** - Invokes `superpowers:systematic-debugging` if critical problems found
4. **Stop** - End command (apply fixes manually later)

## Examples

### Before committing small changes
```
/multi-review --agents quick
```

### Before creating PR
```
/multi-review --agents thorough
```

### Framework-specific review (React/Next.js)
```
/multi-review --agents framework
```

### Comprehensive review with all agents
```
/multi-review --agents comprehensive
```

## Integration with Development Workflow

**Recommended checkpoints:**
- After feature implementation → `/multi-review --agents thorough`
- Before committing → `/multi-review --agents quick`
- Before PR creation → `/multi-review --agents comprehensive`
- After PR feedback → `/multi-review` with post-review fixes

## Tips

- Use `--suggest` to see context-aware agent recommendations
- Parallel mode is faster for comprehensive reviews
- Sequential mode allows agents to build on previous findings
- Framework-specific guidance ensures compliance with project patterns
- Confidence scores help filter false positives (ignore issues with score < 25)
- Use `--evidence-mode` for thorough validation (runs ruff/mypy to verify findings)
- Use `--refresh-cache` to update DSPy prompt calibration (takes 30+ seconds)

## 3-Layer Defense Architecture

This command uses a 3-Layer Defense system to eliminate false positives:

```
/multi-review command
        │
        ▼
┌─────────────────────────────────────┐
│ LAYER 1: Context Injection          │
│ (project_context.py)                │
│                                     │
│ ProjectContext with:                │
│  - PythonConfig (mypy, ruff rules)  │
│  - ShellConfig (strict mode files)  │
│  - TestConfig (patterns, coverage)  │
│  - GitMetadata (changed files)      │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ LAYER 1.5: Prompt Calibration       │
│ (dspy_client.py with caching)       │
│                                     │
│ Calibrated guardrails:              │
│  - DO NOT flag X when Y             │
│  - Focus ONLY on Z                  │
│                                     │
│ Reduction: ~44%                     │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ Agent Execution (Task tool)         │
│ - Calibrated prompts with context   │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ LAYER 2: Post-Filtering             │
│ (finding_filter.py)                 │
│                                     │
│ Typed predicates:                   │
│  - is_shell_strict_mode()           │
│  - is_style_nitpick()               │
│  - is_internal_helper()             │
│  - is_low_value_finding()           │
│                                     │
│ Reduction: +30%                     │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│ LAYER 3: Validation Pass            │
│ (validation_pass.py)                │
│                                     │
│ Cross-reference with tools:         │
│  - Does ruff already catch this?    │
│  - Does mypy contradict this?       │
│  - Does it match project patterns?  │
│                                     │
│ Reduction: +15%                     │
└─────────────────┬───────────────────┘
                  │
                  ▼
         Filtered Results
    (Target: <15% FP rate)
```

**Cache Strategy (FAIL-CLOSED):**
- Pre-compiled prompts at install time
- Hash lookup at runtime (~1ms)
- API NEVER in runtime path (30s latency)
- Manual refresh via `--refresh-cache` only

## Plugin Dependencies

This command requires the following plugins to be installed:
- `feature-dev` plugin for `feature-dev:code-reviewer` agent
- `pr-review-toolkit` plugin for all PR review agents

## See Also

- `/feature-dev:feature-dev` - Full feature development with integrated review
- `/superpowers:receiving-code-review` - How to process review feedback
- `/superpowers:code-review-checklist` - Framework-specific review criteria
