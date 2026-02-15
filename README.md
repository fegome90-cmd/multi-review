# multi-review

Multi-agent code review orchestration with smart agent selection for Claude Code.

## Overview

`multi-review` is a standalone plugin that orchestrates code review agents from multiple plugins:

- **feature-dev** (Official Anthropic) - General code review with confidence scoring
- **pr-review-toolkit** (Official Anthropic) - Specialized PR review agents (7 agents)
- **superpowers** (✅ MIT Licensed) - Framework-specific review guidance

See [DEPENDENCIES.md](DEPENDENCIES.md) for complete dependency and licensing information.


## Installation

```bash
# Install from local marketplace
/plugin marketplace add ~/.claude/plugins/multi-review
/plugin install multi-review@local
```

## Quick Start

### Interactive Mode

```bash
# Interactive mode (prompts for preset)
/multi-review

# Framework-specific review
/multi-review --agents framework

# Custom agent selection
/multi-review --agents custom
```

### Direct Slash Commands (No Questionnaire)

Skip the preset selection and run immediately:

```bash
# Quick check - 2 agents (~30s)
/mr-quick

# Thorough review - 4 agents (~2min)
/mr-thorough

# Comprehensive review - 7 agents (~5min)
/mr-comprehensive
```

### Command Equivalents

| Direct Command | Equivalent To |
|----------------|---------------|
| `/mr-quick` | `/multi-review --agents quick` |
| `/mr-thorough` | `/multi-review --agents thorough` |
| `/mr-comprehensive` | `/multi-review --agents comprehensive` |

### Additional Commands

```bash
# Multi-agent planning & execution
/mr-plan

# Plugin diagnostics
/mr-doctor
```

## Presets

| Preset | Agents | Use Case |
|--------|--------|----------|
| quick | 2 | Fast check before commit |
| thorough | 4 | Balanced review |
| comprehensive | 7 | Complete review before PR |
| framework | 1-2 | Framework-specific compliance |

**All presets use open-source plugins!** See [DEPENDENCIES.md](DEPENDENCIES.md) for details.

## Context Detection

The plugin automatically detects:

- **Change size:** Lines modified (via git diff)
- **File types:** Tests, type definitions, error handlers
- **PR status:** Via gh CLI (optional)

**Suggestions based on context:**

| Context | Suggestion |
|---------|------------|
| < 50 lines | quick preset |
| Has tests | Add test analyzer |
| Has types | Add type analyzer |
| > 500 lines | comprehensive preset |

## Hooks

The plugin includes automated hooks (disabled by default):

### Post-Write Hook
Runs quick review after file writes.

```bash
# Enable in .claude/settings.local.json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/post-write.sh",
        "enabled": true
      }]
    }]
  }
}
```

### Pre-Commit Hook
Runs review before git commit.

```bash
# Enable in .claude/settings.local.json
{
  "hooks": {
    "PreCommit": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pre_commit_check.py",
        "enabled": true
      }]
    }]
  }
}
```

### Session-End Hook
Runs comprehensive review at session end.

```bash
# Enable in .claude/settings.local.json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session_review.py",
        "enabled": true
      }]
    }]
  }
}
```

## Standalone Scripts

All scripts can be run independently:

```bash
# Context detection
python3 ~/.claude/plugins/multi-review/scripts/context_detector.py --suggest

# Post-Write review
python3 ~/.claude/plugins/multi-review/scripts/auto_review.py --file path/to/file.py

# Pre-Commit check
python3 ~/.claude/plugins/multi-review/scripts/pre_commit_check.py --strict

# Session review
python3 ~/.claude/plugins/multi-review/scripts/session_review.py
```

## Reports

Review reports are saved to `~/.claude/plugins/multi-review/reports/`:

- `review_YYYYMMDD-HHMMSS.json` - Post-Write reports
- `commit_YYYYMMDD-HHMMSS.json` - Pre-Commit reports
- `session_YYYYMMDD-HHMMSS.json` - Session-End reports

## Dependencies

Required plugins:
- `feature-dev` - for `feature-dev:code-reviewer`
- `pr-review-toolkit` - for all PR review agents

Optional:
- `superpowers` - for `superpowers:code-review-checklist`

## Architecture

```
multi-review/
├── .claude-plugin/
│   ├── plugin.json          # Plugin metadata
│   ├── marketplace.json      # Marketplace config
│   └── hooks.json           # Hook definitions (disabled by default)
├── commands/
│   ├── multi-review.md      # Main interactive command
│   ├── cm-multi-review.md   # Backward compatibility alias
│   ├── mr-quick.md          # Quick 2-agent review
│   ├── mr-thorough.md       # Thorough 4-agent review
│   ├── mr-comprehensive.md  # Comprehensive 7-agent review
│   ├── mr-plan.md           # Planning & execution (Sprint 2)
│   └── mr-doctor.md         # Plugin diagnostics (Sprint 2)
├── scripts/
│   ├── context_detector.py   # Context detection & agent suggestions
│   ├── auto_review.py        # Post-Write handler
│   ├── pre_commit_check.py   # Pre-Commit handler
│   └── session_review.py     # Session-End handler
├── hooks/
│   ├── post-write.sh         # Post-Write wrapper
│   ├── pre-commit.sh         # Pre-Commit wrapper
│   └── session-end.sh        # Session-End wrapper
├── resources/
│   ├── agent-catalog.md       # Available agents documentation
│   ├── preset-definitions.md  # Preset configurations
│   └── context-detection.md   # Detection logic documentation
├── reports/                   # Review reports (gitignored)
├── README.md                  # This file
└── CLAUDE.md                  # Claude Code guidance
```

## Command Reference

| Command | Agents | Description |
|---------|--------|-------------|
| `/multi-review` | varies | Interactive review with preset selection |
| `/mr-quick` | 2 | Fast check before commits |
| `/mr-thorough` | 4 | Balanced review for features |
| `/mr-comprehensive` | 7 | Complete review before PRs |
| `/mr-plan` | - | Multi-agent planning & execution |
| `/mr-doctor` | - | Plugin diagnostics |

## License

MIT - See [LICENSE](LICENSE) file.

**Important:** This plugin orchestrates agents from external plugins with their own licensing terms. See [DEPENDENCIES.md](DEPENDENCIES.md) for details.

## Author

Felipe Gonzalez
