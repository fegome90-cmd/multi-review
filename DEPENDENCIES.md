# Dependencies

External plugins required for `multi-review` to function.

## Required Plugins

### Official Anthropic Plugins (Bundled with Claude Code)

| Plugin | Agents Used | Purpose |
|--------|-------------|---------|
| **feature-dev** | `feature-dev:code-reviewer` | General code review with confidence scoring |
| **pr-review-toolkit** | 7 specialized agents | PR-specific review (tests, errors, types, comments, simplifier) |

**Installation:** These are included with Claude Code by default. No additional installation needed.

### Optional Plugins

| Plugin | Agents Used | Status | Source |
|--------|-------------|--------|--------|
| **superpowers** | `superpowers:code-review-checklist` | ✅ **MIT Licensed** | obra/superpowers-marketplace |

**superpowers Marketplace:**
- **Repository:** https://github.com/obra/superpowers-marketplace
- **License:** MIT License (Copyright (c) 2025 Jesse Vincent)
- **Installation:** `/plugin marketplace add obra/superpowers-marketplace`

> **Note:** Individual plugins within superpowers may have different licenses. See respective plugin documentation.

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

### superpowers Plugin (MIT Licensed)
```
superpowers:code-review-checklist - Framework-specific review guidance
```

## Preset Dependency Matrix

| Preset | feature-dev | pr-review-toolkit | superpowers | All Plugins Open Source |
|--------|-------------|------------------|-------------|-------------------------|
| **quick** | ✅ Required | ✅ Required | ❌ Not used | ✅ Yes |
| **thorough** | ✅ Required | ✅ Required | ❌ Not used | ✅ Yes |
| **comprehensive** | ✅ Required | ✅ Required | ❌ Not used | ✅ Yes |
| **framework** | ❌ Not used | ✅ Required | ✅ Required | ✅ Yes (MIT) |

**All presets now use open-source plugins only!** ✅

## Installation

### Install superpowers Marketplace (for framework preset)

```bash
# Add the marketplace
/plugin marketplace add obra/superpowers-marketplace

# Install the core superpowers plugin
/plugin install superpowers@superpowers-marketplace
```

### Verify Installation

```bash
# Check installed plugins
/plugin list

# Verify superpowers agents available
/multi-review --list-agents | grep superpowers
```

## Agent Sources and Licenses

| Plugin | Source | License | Repository |
|--------|--------|----------|------------|
| feature-dev | Official Anthropic | Included with Claude Code | Built-in |
| pr-review-toolkit | Official Anthropic | Included with Claude Code | Built-in |
| superpowers | obra/superpowers-marketplace | MIT License | https://github.com/obra/superpowers-marketplace |

## Attribution

This plugin uses agents from:

### Official Anthropic Plugins
- **feature-dev** - General code review
- **pr-review-toolkit** - Specialized PR review agents

### Third-Party Open Source Plugins
- **superpowers** (MIT License)
  - Copyright (c) 2025 Jesse Vincent
  - Repository: https://github.com/obra/superpowers-marketplace
  - Licensed under MIT License - see https://github.com/obra/superpowers-marketplace/blob/main/LICENSE

## License

This plugin (`multi-review`) is released under the MIT License (see LICENSE file).

All required dependencies are either:
1. Official Anthropic plugins (included with Claude Code), or
2. Open source plugins with permissive licenses (MIT)

See each plugin's repository for their specific licensing terms.
