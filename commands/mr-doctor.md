---
description: Diagnose multi-review plugin health
allowed-tools: Bash, Read, Glob, Grep, AskUserQuestion
---

# Multi-Review Doctor (mr-doctor)

Diagnose the health of the multi-review plugin and detect common issues.

## Variables

- `--verbose`: Show detailed output for each check
- `--fix`: Attempt automatic fixes where possible

## Instructions

Run a comprehensive health check on the multi-review plugin.

### Step 1: Define Plugin Root

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/cache/multi-review-dev/multi-review/1.0.0}"
```

### Step 2: Run Verification Checks

Execute each check and collect results:

#### Check 1: Python Scripts Syntax

```bash
echo "## Check 1: Python Scripts Syntax"

scripts=(
  "$PLUGIN_ROOT/scripts/context_detector.py"
  "$PLUGIN_ROOT/scripts/finding_aggregator.py"
  "$PLUGIN_ROOT/scripts/finding_filter.py"
  "$PLUGIN_ROOT/scripts/prompt_cache.py"
)

passed=0
failed=0

for script in "${scripts[@]}"; do
  if [ -f "$script" ]; then
    if python3 -m py_compile "$script" 2>/dev/null; then
      ((passed++))
      [ "$VERBOSE" = "true" ] && echo "  ✓ $(basename $script)"
    else
      ((failed++))
      echo "  ✗ SYNTAX ERROR: $(basename $script)"
    fi
  else
    ((failed++))
    echo "  ✗ NOT FOUND: $(basename $script)"
  fi
done

echo "  Result: $passed passed, $failed failed"
```

#### Check 2: Required Plugins

```bash
echo "## Check 2: Required Plugins"

required_plugins=(
  "feature-dev"
  "pr-review-toolkit"
)

for plugin in "${required_plugins[@]}"; do
  if [ -d "$HOME/.claude/plugins/cache" ]; then
    if ls $HOME/.claude/plugins/cache/*/manifest.json 2>/dev/null | xargs grep -l "\"name\".*\"$plugin\"" > /dev/null 2>&1; then
      echo "  ✓ $plugin: installed"
    else
      echo "  ✗ $plugin: NOT INSTALLED"
      echo "    Fix: /plugin install $plugin"
    fi
  fi
done

# Optional plugin
if ls $HOME/.claude/plugins/cache/*/manifest.json 2>/dev/null | xargs grep -l "\"name\".*\"superpowers\"" > /dev/null 2>&1; then
  echo "  ✓ superpowers: installed (optional)"
else
  echo "  ⚠ superpowers: not installed (optional, for post-review actions)"
fi
```

#### Check 3: Git Available

```bash
echo "## Check 3: Git Available"

if command -v git &> /dev/null; then
  git_version=$(git --version | cut -d' ' -f3)
  echo "  ✓ Git: $git_version"
else
  echo "  ✗ Git: NOT FOUND"
  echo "    Fix: Install git (brew install git)"
fi
```

#### Check 4: gh CLI Available (Optional)

```bash
echo "## Check 4: GitHub CLI (optional)"

if command -v gh &> /dev/null; then
  gh_version=$(gh --version | head -1 | cut -d' ' -f3)
  echo "  ✓ gh CLI: $gh_version"
else
  echo "  ⚠ gh CLI: not installed (optional, for PR features)"
fi
```

#### Check 5: Directory Structure

```bash
echo "## Check 5: Directory Structure"

required_dirs=("commands" "scripts" "resources")
required_files=(
  "commands/multi-review.md"
  "commands/mr-quick.md"
  "commands/mr-thorough.md"
  "commands/mr-comprehensive.md"
  "commands/mr-plan.md"
  "commands/mr-doctor.md"
  "scripts/context_detector.py"
  "scripts/finding_aggregator.py"
  ".claude-plugin/plugin.json"
)

for dir in "${required_dirs[@]}"; do
  if [ -d "$PLUGIN_ROOT/$dir" ]; then
    echo "  ✓ $dir/"
  else
    echo "  ✗ MISSING: $dir/"
  fi
done

for file in "${required_files[@]}"; do
  if [ -f "$PLUGIN_ROOT/$file" ]; then
    [ "$VERBOSE" = "true" ] && echo "  ✓ $file"
  else
    echo "  ✗ MISSING: $file"
  fi
done
```

#### Check 6: Commands Syntax

```bash
echo "## Check 6: Commands Frontmatter"

for cmd in "$PLUGIN_ROOT/commands"/*.md; do
  if [ -f "$cmd" ]; then
    if head -1 "$cmd" | grep -q "^---"; then
      if grep -q "^description:" "$cmd"; then
        [ "$VERBOSE" = "true" ] && echo "  ✓ $(basename $cmd)"
      else
        echo "  ✗ MISSING description: $(basename $cmd)"
      fi
    else
      echo "  ✗ MISSING frontmatter: $(basename $cmd)"
    fi
  fi
done
```

### Step 3: Summarize Results

```bash
echo ""
echo "## Summary"
echo ""
echo "Multi-review plugin health check complete."
echo ""
echo "If issues were found:"
echo "  1. Install missing plugins: /plugin install <name>"
echo "  2. Reinstall multi-review: /plugin uninstall multi-review@local && /plugin install multi-review@local"
echo "  3. Check file permissions if scripts are not executable"
```

## Quick Diagnostic

For a fast check without verbose output:

```bash
# Run all checks
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/cache/multi-review-dev/multi-review/1.0.0}"

echo "# Multi-Review Quick Check"
echo ""

# Python syntax
echo -n "Python scripts: "
python3 -m py_compile "$PLUGIN_ROOT/scripts/context_detector.py" 2>/dev/null && echo "✓" || echo "✗"

# Git
echo -n "Git: "
command -v git &> /dev/null && echo "✓ $(git --version | cut -d' ' -f3)" || echo "✗"

# Directory
echo -n "Plugin directory: "
[ -d "$PLUGIN_ROOT" ] && echo "✓" || echo "✗ NOT FOUND"
```

## Usage Examples

```bash
# Standard health check
/mr-doctor

# Verbose output
/mr-doctor --verbose
```

## Common Issues and Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Scripts not found | Plugin not installed | `/plugin install multi-review@local` |
| Syntax errors in scripts | Corrupted files | Reinstall plugin |
| Missing plugins | Dependencies not installed | `/plugin install feature-dev` |
| Git not found | git not in PATH | `brew install git` |
| Missing frontmatter | Command file corrupted | Reinstall plugin |

## See Also

- `/mr-quick` - 2-agent fast review
- `/mr-thorough` - 4-agent balanced review
- `/mr-comprehensive` - 7-agent complete review
- `/mr-plan` - Multi-agent planning
