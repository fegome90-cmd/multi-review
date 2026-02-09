# Context Detection

How multi-review detects repository context to suggest appropriate agents.

## Detection Methods

### Git Status
- **Staged files:** `git diff --cached --name-only`
- **Working files:** `git diff --name-only`
- **Change size:** `git diff --cached --shortstat` (insertion count)

### GitHub CLI (Optional)
- **PR detection:** `gh pr view --json state`
- **Benefits:** PR-aware suggestions when available

## Detected Patterns

### File Type Patterns

**Test files:**
- `_test.py`, `_test.ts`
- `.test.ts`, `.spec.ts`
- `__tests__.py`, `tests/`

**Type definitions:**
- `_types.ts`, `.d.ts`
- `types.py`, `types.ts`

**Error handling:**
- File paths containing: `error`, `exception`, `handler`

## Change Size Thresholds

| Size (lines) | Classification | Preset Suggestion |
|--------------|----------------|-------------------|
| 0-49 | Small | quick |
| 50-499 | Medium | thorough or context-based |
| 500+ | Large | comprehensive |

## Suggestion Logic

```
IF change_size < 50:
    RETURN quick preset
ELSE IF change_size > 500:
    RETURN comprehensive preset
ELSE:
    agents = [feature-dev:code-reviewer]
    IF has_tests:
        agents += [pr-review-toolkit:pr-test-analyzer]
    IF has_types:
        agents += [pr-review-toolkit:type-design-analyzer]
    IF has_error_handling:
        agents += [pr-review-toolkit:silent-failure-hunter]
    RETURN agents
```

## Error Handling

The context detector gracefully handles:

- **gh CLI not found:** PR detection skipped, continues with git-only
- **Not in git repo:** Returns partial context with warning
- **Git timeout:** Returns partial context after timeout
- **Corrupted git:** Provides actionable error message

## Usage Examples

```bash
# Get context-aware suggestions
python3 ~/.claude/plugins/multi-review/scripts/context_detector.py --suggest

# List all available agents
python3 ~/.claude/plugins/multi-review/scripts/context_detector.py --list

# Show available presets
python3 ~/.claude/plugins/multi-review/scripts/context_detector.py --presets

# Show detected context
python3 ~/.claude/plugins/multi-review/scripts/context_detector.py --context
```
