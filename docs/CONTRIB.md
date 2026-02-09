# Contributing to multi-review

Development workflow and setup guide for the `multi-review` plugin.

## Development Environment

**Prerequisites:**
- Python 3.10+
- Claude Code CLI
- Git (for context detection)
- GitHub CLI (optional, for PR context)

**Setup:**

```bash
# Clone or navigate to plugin directory
cd ~/.claude/plugins/multi-review

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (uses uv for fast dependency management)
uv pip install -e .
```

## Project Structure

```
multi-review/
├── .claude-plugin/
│   ├── plugin.json          # Plugin metadata
│   ├── marketplace.json      # Marketplace config
│   └── hooks.json           # Hook definitions (disabled by default)
├── commands/
│   ├── multi-review.md      # Main slash command
│   └── cm-multi-review.md   # Legacy alias (deprecated)
├── scripts/
│   ├── context_detector.py   # Context detection & agent suggestions
│   ├── auto_review.py        # Post-Write handler
│   ├── pre_commit_check.py   # Pre-Commit handler
│   ├── session_review.py     # Session-End handler
│   └── utils.py              # Shared utilities
├── hooks/
│   ├── post-write.sh         # Post-Write wrapper
│   ├── pre-commit.sh         # Pre-Commit wrapper
│   └── session-end.sh        # Session-End wrapper
├── resources/
│   ├── agent-catalog.md       # Available agents documentation
│   ├── preset-definitions.md  # Preset configurations
│   └── context-detection.md   # Detection logic documentation
├── tests/
│   ├── test_context_detector.py
│   ├── test_auto_review.py
│   └── test_utils.py
├── docs/
│   ├── CONTRIB.md            # This file
│   └── plans/                # Implementation plans
├── reports/                   # Review reports (gitignored)
├── pyproject.toml            # Python project config
├── CLAUDE.md                 # Claude Code guidance
└── README.md                 # User documentation
```

## Testing

**Run all tests:**

```bash
pytest
```

**Run specific test file:**

```bash
pytest tests/test_context_detector.py
```

**Run with coverage:**

```bash
pytest --cov=scripts --cov-report=term-missing
```

**Run integration tests (requires git/gh CLI):**

```bash
pytest -m integration
```

**Run unit tests only:**

```bash
pytest -m unit
```

## Test Development Workflow

1. **Write test first** (TDD)
2. **Run test** - should fail (RED)
3. **Implement feature** - test passes (GREEN)
4. **Refactor** - improve code (REFACTOR)
5. **Verify coverage** - aim for 80%+

## Code Quality

**Type checking:**

```bash
mypy scripts/
```

**Linting:**

```bash
ruff check scripts/
```

**Auto-fix lint issues:**

```bash
ruff check --fix scripts/
```

## Plugin Testing

**Install locally for testing:**

```bash
# Add to marketplace
/plugin marketplace add ~/.claude/plugins/multi-review

# Install plugin
/plugin install multi-review@local

# Test command
/multi-review
```

**Reinstall after changes:**

```bash
# Uninstall
/plugin uninstall multi-review@local

# Reinstall
/plugin install multi-review@local

# Restart Claude Code if command schema changes
```

## Scripts

Available standalone scripts:

| Script | Purpose | Usage |
|--------|---------|-------|
| `context_detector.py` | Detect context & suggest agents | `python3 scripts/context_detector.py --suggest` |
| `auto_review.py` | Post-Write review handler | `python3 scripts/auto_review.py --file path/to/file.py` |
| `pre_commit_check.py` | Pre-Commit review handler | `python3 scripts/pre_commit_check.py --strict` |
| `session_review.py` | Session-End review handler | `python3 scripts/session_review.py` |

## Hooks Configuration

Hooks are **disabled by default**. Enable via `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/post-write.sh",
        "enabled": true
      }]
    }],
    "PreCommit": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/pre_commit_check.py",
        "enabled": true
      }]
    }],
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

## Commit Messages

Follow conventional commits format:

```
<type>: <description>

<optional body>
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `refactor` - Code refactoring
- `docs` - Documentation
- `test` - Tests
- `chore` - Maintenance

**Examples:**
```
feat: add framework-specific preset
fix: correct context detection for merged PRs
docs: update README with migration notice
```

## Key Invariants

These rules must ALWAYS hold:

1. **Zero external dependencies** - Scripts use only Python stdlib
2. **Stdlib logging only** - No `infrastructure.logging` (from context-memory)
3. **Backward compatibility** - `/cm-multi-review` must still work (with deprecation warning)
4. **Hooks disabled by default** - Users must opt-in via settings.json
5. **Agent orchestration only** - Plugin does NOT create its own review agents
6. **Git-based detection** - Uses git/gh CLI for context (no LSP dependency in MVP)

## Pull Request Process

1. **Branch naming** - Use descriptive names: `feat/add-preset`, `fix/context-detection`
2. **Write tests** - Ensure all tests pass
3. **Update docs** - Keep CLAUDE.md and README.md in sync
4. **Commit** - Use conventional commit format
5. **Push** - Create PR with clear description

## Adding New Agents

1. **Update `resources/agent-catalog.md`** - Document agent capabilities
2. **Update `resources/preset-definitions.md`** - Add to appropriate presets
3. **Update `scripts/context_detector.py`** - Add detection logic if needed
4. **Add tests** - Test new agent selection logic
5. **Update docs** - Document use cases

## Questions?

- See `CLAUDE.md` for Claude Code guidance
- See `README.md` for user documentation
- Check `resources/` for detailed documentation on agents, presets, and detection
