# multi-review

Multi-agent code review orchestration with smart agent selection for Claude Code.

## Overview

`multi-review` is a standalone plugin that orchestrates code review agents from multiple plugins:

- **feature-dev** (Official Anthropic) - General code review with confidence scoring
- **pr-review-toolkit** (Official Anthropic) - Specialized PR review agents (7 agents)
- **superpowers** (✅ MIT Licensed) - Framework-specific review guidance

See [DEPENDENCIES.md](DEPENDENCIES.md) for complete dependency and licensing information.

## Migration Notice

This plugin was migrated from `cm-multi-review` (previously part of `context-memory`).

**Breaking changes:**
- Command renamed from `/cm-multi-review` to `/multi-review`
- Now requires standalone installation

**Deprecation:**
- `/cm-multi-review` will show a deprecation warning
- Migrate to `/multi-review` for continued support

## Installation

```bash
# Install from local marketplace
/plugin marketplace add ~/.claude/plugins/multi-review
/plugin install multi-review@local
```

## Quick Start

```bash
# Interactive mode (prompts for preset)
/multi-review

# Quick check - 2 agents
/multi-review --agents quick

# Thorough review - 4 agents
/multi-review --agents thorough

# Comprehensive review - 7 agents
/multi-review --agents comprehensive

# Framework-specific review
/multi-review --agents framework

# Custom agent selection
/multi-review --agents custom
```

## Presets

| Preset | Agents | Use Case |
|--------|--------|----------|
| quick | 1-2 | Fast check before commit |
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
│   └── multi-review.md      # Main slash command
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

## License

MIT - See [LICENSE](LICENSE) file.

**Important:** This plugin orchestrates agents from external plugins with their own licensing terms. See [DEPENDENCIES.md](DEPENDENCIES.md) for details.

## Author

Felipe Gonzalez
