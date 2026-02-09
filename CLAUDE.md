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

#### scripts/utils.py

Shared utility module providing common functionality across all hook scripts. This module eliminates code duplication and ensures consistent behavior.

**ExitCodes Class**

Canonical exit code constants for all scripts:
- `ExitCodes.SUCCESS` (0): Normal successful execution
- `ExitCodes.FAILURE` (1): General failure or issues found
- `ExitCodes.INVALID_ARGS` (2): Invalid command-line arguments
- `ExitCodes.CONFIG_ERROR` (3): Configuration or setup error

Legacy constants (deprecated, use ExitCodes class instead):
- `EXIT_SUCCESS`, `EXIT_ISSUES_FOUND`, `EXIT_ERROR`, `EXIT_TYPE_ERRORS`

**Core Functions**

- `save_report(report_data, report_type, prefix="review")` - Save report to reports directory as JSON. Returns Path or None on failure.
- `get_reports_dir()` - Get/create the reports directory. Returns Path.
- `generate_timestamp()` - Generate timestamp for filenames (YYYYMMDD-HHMMSS format).
- `format_report_summary(preset, agents, issues_found, critical_count)` - Format standard report summary dictionary.
- `log_review_summary(preset, agents, issues_found, report_path)` - Log standardized review summary.
- `validate_file_path(file_path)` - Validate file exists and is readable. Returns bool.
- `count_lines_safely(file_path)` - Count lines with comprehensive error handling (PermissionError, UnicodeDecodeError, OSError).

**Usage Example**

```python
from scripts.utils import ExitCodes, save_report, log_review_summary

# Save report
report_data = {"results": [], "summary": {...}}
path = save_report(report_data, "commit")
if path:
    log_review_summary("standard", ["code-reviewer"], 5, path)

# Exit with proper code
sys.exit(ExitCodes.SUCCESS)
```

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
