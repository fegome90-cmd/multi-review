# CLAUDE.md

Guidance for Claude Code when working on the `multi-review` plugin.

---

## Quick Start

```bash
# Install locally
/plugin marketplace add ~/.claude/plugins/multi-review
/plugin install multi-review@local

# Run review
/multi-review
```

---

## Architecture Overview

**Multi-agent orchestration plugin** that coordinates code review agents from multiple plugins (feature-dev, pr-review-toolkit, superpowers).

**Workflow:** Detect context → Suggest preset → Launch agents → Aggregate results → Offer next actions

See `README.md` for complete documentation.

---

## Key Invariants

These rules must ALWAYS hold:

1. **Zero external dependencies** - Scripts use only Python stdlib
2. **Stdlib logging only** - No infrastructure.logging
3. **Backward compatibility** - `/cm-multi-review` still works (with deprecation warning)
4. **Hooks disabled by default** - Users must opt-in via settings.json
5. **Agent orchestration only** - Plugin does NOT create its own review agents
6. **Git-based detection** - Uses git/gh CLI (no LSP dependency in MVP)

---

## Development Workflow

1. **Edit component** - Modify command/script/resource files
2. **Uninstall** - `/plugin uninstall multi-review@local`
3. **Reinstall** - `/plugin install multi-review@local`
4. **Test** - `/multi-review` in target project
5. **Restart** - Claude Code if command schema changes

---

## Component Guidelines

### Command Frontmatter (`commands/*.md`)
See `resources/command-format.md` for specification.

### Hooks (`.claude-plugin/hooks.json`)
See `resources/hook-format.md` for specification.

### Python Scripts
- Use `logging.basicConfig(level=logging.INFO)` - stdlib only
- Exit codes: 0=success, 1=issues, 2=error
- Comprehensive try/except with actionable messages

See `docs/SCRIPTS_REFERENCE.md` for complete API.

### Bash Wrappers
- Set `set -euo pipefail`
- Find plugin root: `PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`
- Pass through exit codes: `exit $exit_code`

---

## Source of Truth

- **README.md** - Complete plugin documentation
- **DEPENDENCIES.md** - Required plugins and licensing (⚠️ IMPORTANT)
- **docs/CONTRIB.md** - Development workflow and testing
- **docs/RUNBOOK.md** - Deployment and troubleshooting
- **docs/SCRIPTS_REFERENCE.md** - Complete scripts API
- **resources/agent-catalog.md** - Available agents
- **resources/preset-definitions.md** - Preset configurations
