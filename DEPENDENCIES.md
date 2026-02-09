# Dependencies

External plugins required for `multi-review` to function.

## Required Plugins

### Official Anthropic Plugins (Bundled with Claude Code)

| Plugin | Agents Used | Purpose |
|--------|-------------|---------|
| **feature-dev** | `feature-dev:code-reviewer` | General code review with confidence scoring |
| **pr-review-toolkit** | 7 specialized agents | PR-specific review (tests, errors, types, comments, simplifier) |

**Installation:** These are included with Claude Code by default. No additional installation needed.

### Optional Third-Party Plugins

| Plugin | Agents Used | Status | Notes |
|--------|-------------|--------|-------|
| **superpowers** | `superpowers:code-review-checklist` | ⚠️ **NOT OPEN SOURCE** | Framework-specific review guidance |

**IMPORTANT - Legal Notice:**
- `superpowers` is **NOT open source** software
- Using agents from this plugin may have licensing implications
- The `framework` preset requires this plugin (optional feature)
- All other presets work WITHOUT superpowers

**Recommendation:** Use `quick`, `thorough`, or `comprehensive` presets to avoid superpowers dependency.

## Agent Breakdown by Plugin

### feature-dev Plugin
```
feature-dev:code-reviewer - General code review with confidence scoring
```

### pr-review-toolkit Plugin (Official Anthropic)
```
pr-review-toolkit:code-reviewer         - Project guidelines review
pr-review-toolkit:pr-test-analyzer      - Test coverage quality
pr-review-toolkit:silent-failure-hunter - Error handling detection
pr-review-toolkit:type-design-analyzer  - Type system quality
pr-review-toolkit:comment-analyzer      - Documentation accuracy
pr-review-toolkit:code-simplifier       - Refactoring suggestions
```

### superpowers Plugin (⚠️ NOT OPEN SOURCE)
```
superpowers:code-review-checklist - Framework-specific review guidance
```

## Preset Dependency Matrix

| Preset | feature-dev | pr-review-toolkit | superpowers | Legal Status |
|--------|-------------|------------------|-------------|--------------|
| **quick** | ✅ Required | ✅ Required | ❌ Not used | ✅ Safe (official plugins only) |
| **thorough** | ✅ Required | ✅ Required | ❌ Not used | ✅ Safe (official plugins only) |
| **comprehensive** | ✅ Required | ✅ Required | ❌ Not used | ✅ Safe (official plugins only) |
| **framework** | ❌ Not used | ✅ Required | ✅ Required | ⚠️ **Requires superpowers** |

## Troubleshooting

### "Agent not found" Error

**Cause:** Required plugin not installed.

**Solution:**
```bash
# Check installed plugins
/plugin list

# Install official plugins (should be pre-installed)
/plugin install feature-dev
/plugin install pr-review-toolkit

# For framework preset only:
# WARNING: superpowers is NOT open source
# Install at your own legal risk
/plugin install superpowers
```

### Use Without superpowers

**Recommended:** Avoid the `framework` preset. Use `quick`, `thorough`, or `comprehensive` instead:

```bash
# Safe - uses official plugins only
/multi-review --agents quick
/multi-review --agents thorough
/multi-review --agents comprehensive

# Avoid - requires non-open-source plugin
# /multi-review --agents framework
```

## Legal Notice

This plugin (`multi-review`) is released under the MIT License (see LICENSE file).

However, **this plugin orchestrates agents from other plugins** which may have their own licensing terms:

- **feature-dev** and **pr-review-toolkit** are official Anthropic plugins included with Claude Code
- **superpowers** is a third-party plugin that is **NOT open source**

**Users are responsible for:**
1. Ensuring they have rights to use all required plugins
2. Complying with each plugin's licensing terms
3. Understanding that `framework` preset requires superpowers (non-open-source)

**No warranty:** This plugin is provided "as is" without warranty of any kind.

## Attribution

This plugin uses agents from:
- **Anthropic** - feature-dev, pr-review-toolkit (official plugins)
- **Third-party** - superpowers (optional, NOT open source)

See each plugin's documentation for their specific licensing terms.
