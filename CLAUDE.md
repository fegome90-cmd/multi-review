# CLAUDE.md

Guidance for Claude Code when working on the `multi-review` plugin.

---

## Quick Start

```bash
# Install locally for development
/plugin marketplace add ~/.claude/plugins/multi-review
/plugin install multi-review@local

# Run review on current directory
/multi-review

# Run with specific preset
/multi-review --agents thorough
```

---

## Plugin Architecture

`multi-review` is a multi-agent code review orchestration plugin that coordinates agents from multiple plugins:

- **feature-dev** - General code review
- **pr-review-toolkit** - Specialized PR review (7 agents)
- **superpowers** - Framework-specific guidance

**Components:**
- `commands/multi-review.md` - Main slash command
- `scripts/context_detector.py` - Git-based context detection
- `scripts/auto_review.py` - Post-Write hook handler
- `scripts/pre_commit_check.py` - Pre-Commit hook handler
- `scripts/session_review.py` - Session-End hook handler
- `hooks/*.sh` - Bash wrapper scripts
- `resources/` - Documentation and reference

**Workflow:**
1. Command detects context using git/gh CLI
2. Suggests preset based on change size + file types
3. Launches agents in parallel via Task tool
4. Aggregates results by severity + confidence
5. Offers next actions (apply fixes, plan, debug, stop)

---

## Development Workflow

1. **Edit component** - Modify command/script/resource files
2. **Uninstall** - `/plugin uninstall multi-review@local`
3. **Reinstall** - `/plugin install multi-review@local`
4. **Test** - `/multi-review` in a target project
5. **Restart** - Restart Claude Code if command schema changes

---

## Key Invariants

These rules must ALWAYS hold:

1. **Zero external dependencies** - Scripts use only Python stdlib
2. **Stdlib logging only** - No infrastructure.logging (from context-memory)
3. **Backward compatibility** - `/cm-multi-review` must still work (with deprecation warning)
4. **Hooks disabled by default** - Users must opt-in via settings.json
5. **Agent orchestration only** - Plugin does NOT create its own review agents
6. **Git-based detection** - Uses git/gh CLI for context (no LSP dependency in MVP)

---

## Component Format

### Command Frontmatter (`commands/*.md`)
```yaml
---
description: Brief description
argument-hint: [--flag=value]
allowed-tools: ["Tool", "AnotherTool"]
---
```

### Hooks (`.claude-plugin/hooks.json`)
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/post-write.sh",
        "enabled": false
      }]
    }],
    "PreCommit": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pre_commit_check.py",
        "enabled": false
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/session_review.py",
        "enabled": false
      }]
    }]
  }
}
```

---

## Script Guidelines

### Python Scripts

- **Use stdlib logging:** `logging.basicConfig(level=logging.INFO)`
- **No external dependencies:** Only Python 3.10+ stdlib
- **Exit codes:** 0=success, 1=issues, 2=error
- **Error handling:** Comprehensive try/except with actionable messages

### Bash Wrappers

- **Set strict mode:** `set -euo pipefail`
- **Find plugin root:** `PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`
- **Pass through exit codes:** `exit $exit_code`

---

## Resources Reference

| Resource | Purpose |
|---|---|
| `agent-catalog.md` | Available agents documentation |
| `preset-definitions.md` | Preset configurations |
| `context-detection.md` | Detection logic documentation |

---

## Migration from cm-multi-review

**Changes:**
1. Command renamed: `/cm-multi-review` → `/multi-review`
2. Plugin standalone (no longer part of context-memory)
3. Scripts use stdlib logging (not infrastructure.logging)
4. Hooks disabled by default

**Compatibility:**
- Original `/cm-multi-review` still works (shows deprecation warning)
- Update context-memory to add deprecation notice to original command

---

## Additional Context

- `README.md` - Complete plugin documentation
- `reports/` - Historical review reports
