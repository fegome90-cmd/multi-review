# multi-review Runbook

Operational procedures for monitoring, troubleshooting, and maintaining the `multi-review` plugin.

## Deployment Procedures

### Initial Installation

```bash
# Add to local marketplace
/plugin marketplace add ~/.claude/plugins/multi-review

# Install plugin
/plugin install multi-review@local

# Verify installation
/plugin list | grep multi-review
```

### Update Plugin After Changes

```bash
# Uninstall current version
/plugin uninstall multi-review@local

# Reinstall from local source
/plugin install multi-review@local

# Restart Claude Code if command schema changes
# (e.g., if argument-hint or allowed-tools changed)
```

### Enable Hooks (Optional)

Hooks are **disabled by default** for user control. Enable via `.claude/settings.local.json`:

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

**Individual hook control:**
- Set `enabled: false` for any hook you don't want
- Remove entire hook block to disable all hooks

## Monitoring

### Review Reports

Reports are saved to `~/.claude/plugins/multi-review/reports/`:

| Report Type | Filename Pattern | Trigger |
|-------------|------------------|---------|
| Post-Write | `review_YYYYMMDD-HHMMSS.json` | After file writes |
| Pre-Commit | `commit_YYYYMMDD-HHMMSS.json` | Before git commit |
| Session-End | `session_YYYYMMDD-HHMMSS.json` | At session end |

**Monitor report volume:**

```bash
# Count reports by type
ls -1 ~/.claude/plugins/multi-review/reports/review_*.json | wc -l
ls -1 ~/.claude/plugins/multi-review/reports/commit_*.json | wc -l
ls -1 ~/.claude/plugins/multi-review/reports/session_*.json | wc -l
```

**Clean old reports:**

```bash
# Remove reports older than 30 days
find ~/.claude/plugins/multi-review/reports/ -name "*.json" -mtime +30 -delete
```

### Log Monitoring

Scripts use Python stdlib `logging` module:

```bash
# View recent logs (if log files are configured)
tail -f ~/.claude/plugins/multi-review/logs/*.log
```

## Common Issues and Fixes

### Issue: Command Not Found

**Symptom:** `/multi-review` returns "Unknown command"

**Diagnosis:**
```bash
/plugin list | grep multi-review
```

**Fix:**
```bash
/plugin install multi-review@local
```

### Issue: Hooks Not Running

**Symptom:** No review reports generated after expected triggers

**Diagnosis:**
1. Check hook enabled status in `.claude/settings.local.json`
2. Verify script permissions: `ls -la ~/.claude/plugins/multi-review/hooks/*.sh`
3. Check script manually: `bash ~/.claude/plugins/multi-review/hooks/post-write.sh`

**Fix:**
```bash
# Ensure hooks are executable
chmod +x ~/.claude/plugins/multi-review/hooks/*.sh

# Verify settings.json has "enabled": true
# Restart Claude Code after changing settings
```

### Issue: Context Detection Fails

**Symptom:** "Unable to detect git context" or similar errors

**Diagnosis:**
```bash
# Check git is available
git --version

# Check current directory is a git repo
git status
```

**Fix:**
```bash
# Initialize git if needed
git init

# Or run multi-review with explicit preset
/multi-review --agents quick
```

### Issue: Agent Not Available

**Symptom:** "Agent xxx not found"

**Diagnosis:**
1. Check if required plugin is installed: `/plugin list`
2. Verify agent name in `resources/agent-catalog.md`

**Fix:**
```bash
# Install missing plugin
/plugin install <required-plugin>@latest

# Or use different preset with available agents
/multi-review --agents quick
```

### Issue: Slow Performance

**Symptom:** Long delays before review starts

**Possible Causes:**
- Large git diff (>1000 files)
- Comprehensive preset (7 agents)
- Network latency (if agents require external calls)

**Fix:**
```bash
# Use quicker preset
/multi-review --agents quick

# Limit scope to specific files
/multi-review --agents quick -- src/

# Disable hooks temporarily
# Set "enabled": false in settings.json
```

## Rollback Procedures

### Rollback Plugin Installation

```bash
# Uninstall current version
/plugin uninstall multi-review@local

# Reinstall from specific commit
cd ~/.claude/plugins/multi-review
git checkout <commit-hash>
/plugin install multi-review@local
```

### Rollback Hook Changes

```bash
# Edit .claude/settings.local.json
# Set "enabled": false for problematic hooks
# Or restore previous settings.json from backup
```

## Maintenance Tasks

### Weekly

- [ ] Review and clean old reports (>30 days)
- [ ] Check for plugin updates: `cd ~/.claude/plugins/multi-review && git pull`
- [ ] Verify tests pass: `pytest`

### Monthly

- [ ] Review and update agent catalog (`resources/agent-catalog.md`)
- [ ] Check for deprecated agents and update presets
- [ ] Review documentation for accuracy

### As Needed

- [ ] Add new agents to catalog as they become available
- [ ] Update preset definitions based on user feedback
- [ ] Fix bugs reported by users

## Troubleshooting Commands

```bash
# Verify plugin structure
ls -la ~/.claude/plugins/multi-review/

# Check Python dependencies
python3 -c "import sys; print(sys.version)"

# Run tests
cd ~/.claude/plugins/multi-review && pytest

# Check git status
cd ~/.claude/plugins/multi-review && git status

# View recent reports
ls -lt ~/.claude/plugins/multi-review/reports/ | head -20

# Check hook scripts
for f in ~/.claude/plugins/multi-review/hooks/*.sh; do
    echo "=== $f ==="
    head -5 "$f"
done
```

## Performance Tuning

### Reduce Review Latency

1. **Use smaller presets:** `quick` instead of `comprehensive`
2. **Disable unused hooks:** Only enable hooks you actually use
3. **Limit git diff scope:** Run from subdirectory instead of repo root

### Optimize Report Storage

1. **Regular cleanup:** Remove old reports periodically
2. **Compress old reports:** `gzip ~/.claude/plugins/multi-review/reports/*.json`
3. **Archive to external storage:** Move reports to long-term storage

## Support and Resources

- **Documentation:** `README.md`, `CLAUDE.md`, `docs/CONTRIB.md`
- **Agent Catalog:** `resources/agent-catalog.md`
- **Issue Tracking:** GitHub Issues (https://github.com/fegome90-cmd/multi-review/issues)
- **Contributing:** See `docs/CONTRIB.md`

## Escalation Path

1. **Check this runbook** - Most issues have documented fixes
2. **Review error logs** - Check reports and hook script output
3. **Check documentation** - `resources/` folder has detailed docs
4. **Open GitHub issue** - Include error details and reproduction steps
