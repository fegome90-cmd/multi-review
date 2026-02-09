# Command Format Specification

Format for Claude Code plugin command files.

## Command Frontmatter (`commands/*.md`)

```yaml
---
description: Brief description of what the command does
argument-hint: [--flag=value] | [optional-arg]
allowed-tools: ["Tool", "AnotherTool", "Task"]
---
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `description` | Yes | Short description shown in command palette |
| `argument-hint` | No | Hint for arguments (shown in UI) |
| `allowed-tools` | No | Tools this command can use (for permissions) |

## Example

```yaml
---
description: Multi-agent code review with smart agent selection
argument-hint: [--agents=quick|thorough|comprehensive|framework]
allowed-tools: ["Task", "Bash", "AskUserQuestion"]
---
```

## Command Body

After the frontmatter, write the command behavior in markdown. Claude will interpret this as instructions.

**Best practices:**
- Start with a brief overview
- Use bullet points for steps
- Include error handling guidance
- Reference external resources for details

## See Also

- `CLAUDE.md` - Plugin guidance
- `README.md` - User documentation
