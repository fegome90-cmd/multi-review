# Hook Format Specification

Format for Claude Code plugin hooks (`.claude-plugin/hooks.json`).

## Structure

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

## Hook Types

| Hook Type | Trigger | Use Case |
|-----------|---------|----------|
| `PostToolUse` | After Write/Edit tools | Review file changes |
| `PreCommit` | Before git commit | Validate before commit |
| `Stop` | When Claude Code exits | Session summary |

## Fields

| Field | Required | Description |
|-------|----------|-------------|
| `matcher` | Yes | Regex for tool names (PostToolUse only) |
| `type` | Yes | Must be "command" |
| `command` | Yes | Shell command to execute |
| `enabled` | Yes | Whether hook is active |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `${CLAUDE_PLUGIN_ROOT}` | Absolute path to plugin directory |
| `${CLAUDE_SESSION_FILE}` | Path to session context file |

## Exit Codes

Scripts should return:
- `0` - Success (continue operation)
- `1` - Issues found (may block or warn)
- `2` - Error (blocks operation)

## Default Behavior

**Hooks are disabled by default** (`enabled: false`). Users must opt-in via `.claude/settings.local.json`.

## See Also

- `docs/RUNBOOK.md` - Hook configuration examples
- `docs/SCRIPTS_REFERENCE.md` - Script API documentation
