---
description: Interactive multi-agent code review with smart agent selection
argument-hint: [--agents AGENTS]
allowed-tools: Skill, Task, TaskOutput, AskUserQuestion, Bash, Read
---

# Multi-Agent Code Review (DEPRECATED)

> **DEPRECATION NOTICE:** This command has been renamed to `/multi-review`.
> Please use `/multi-review` instead. This command will be removed in a future version.

---

Run comprehensive code reviews using multiple specialized agents with interactive configuration.

## Variables

- `--agents AGENTS`: Comma-separated agent list or preset name (optional, prompts if not provided)

## Instructions

**IMPORTANT:** Please use `/multi-review` instead of `/cm-multi-review`.

To continue with your review, run:

```bash
/multi-review
```

Or with a preset:

```bash
/multi-review --agents quick
/multi-review --agents thorough
/multi-review --agents comprehensive
```

## Migration Guide

| Old Command | New Command |
|-------------|-------------|
| `/cm-multi-review` | `/multi-review` |
| `/cm-multi-review --agents quick` | `/multi-review --agents quick` |
| `/cm-multi-review --agents thorough` | `/multi-review --agents thorough` |
| `/cm-multi-review --agents comprehensive` | `/multi-review --agents comprehensive` |

All functionality remains the same. Only the command name has changed.

---

If you'd like to proceed with the review anyway, the full documentation is available in `/multi-review`.
