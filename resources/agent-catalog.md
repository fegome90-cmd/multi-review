# Agent Catalog

Available agents for multi-review orchestration.

## Primary Agents

### feature-dev:code-reviewer
- **Source:** feature-dev plugin
- **Purpose:** General code review with confidence scoring
- **Use when:** You need broad code review coverage
- **Confidence scoring:** 0-100 based on verification level

## Specialized Agents (pr-review-toolkit)

### pr-review-toolkit:code-reviewer
- **Purpose:** Project guidelines compliance review
- **Use when:** Checking adherence to project conventions
- **Focus:** CLAUDE.md, coding standards, project patterns

### pr-review-toolkit:pr-test-analyzer
- **Purpose:** Test coverage quality and completeness
- **Use when:** Test files were modified or added
- **Focus:** Missing edge cases, coverage gaps, test quality

### pr-review-toolkit:silent-failure-hunter
- **Purpose:** Error handling and silent failures detection
- **Use when:** Error handling code was modified
- **Focus:** Swallowed errors, missing error handling, silent failures

### pr-review-toolkit:type-design-analyzer
- **Purpose:** Type design quality and invariants
- **Use when:** Type definitions were modified
- **Focus:** Encapsulation, invariants, type safety

### pr-review-toolkit:comment-analyzer
- **Purpose:** Code comment accuracy and maintainability
- **Use when:** Documentation or comments were modified
- **Focus:** Comment accuracy, outdated docs, maintainability

### pr-review-toolkit:code-simplifier
- **Purpose:** Code simplification and refactoring
- **Use when:** Code complexity increased
- **Focus:** Extract functions, reduce complexity, improve readability

## Framework Agents

### superpowers:code-review-checklist
- **Source:** superpowers plugin
- **Purpose:** Framework-specific review guidance
- **Use when:** Working with specific frameworks (React, Django, etc.)
- **Focus:** Framework best practices and patterns
