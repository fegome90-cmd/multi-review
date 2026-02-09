# Preset Definitions

Pre-configured agent combinations for different review scenarios.

## Presets Overview

| Preset | Agent Count | Use Case | Estimated Time |
|--------|-------------|----------|----------------|
| quick | 1-2 | Fast check before commit | ~30s |
| thorough | 4 | Balanced review for medium changes | ~2min |
| comprehensive | 7 | Complete review before PR | ~5min |
| framework | 1-2 | Framework-specific compliance | ~1min |

## Preset Details

### quick
**Best for:** Small changes (<50 lines), quick sanity check

**Agents:**
1. feature-dev:code-reviewer - General review

**Exit criteria:** Fast feedback on critical issues only

### thorough
**Best for:** Medium changes, feature implementation

**Agents:**
1. feature-dev:code-reviewer - General review
2. pr-review-toolkit:pr-test-analyzer - Test coverage
3. pr-review-toolkit:silent-failure-hunter - Error handling
4. pr-review-toolkit:code-simplifier - Refactoring

**Exit criteria:** Balanced coverage of common issue areas

### comprehensive
**Best for:** Large changes (>500 lines), PR creation

**Agents:**
1. feature-dev:code-reviewer - General review
2. pr-review-toolkit:code-reviewer - Guidelines compliance
3. pr-review-toolkit:pr-test-analyzer - Test coverage
4. pr-review-toolkit:silent-failure-hunter - Error handling
5. pr-review-toolkit:type-design-analyzer - Type design
6. pr-review-toolkit:comment-analyzer - Documentation
7. pr-review-toolkit:code-simplifier - Refactoring

**Exit criteria:** Complete review across all quality dimensions

### framework
**Best for:** Framework-specific code (React, Django, etc.)

**Agents:**
1. superpowers:code-review-checklist - Framework patterns
2. pr-review-toolkit:code-simplifier - Refactoring

**Exit criteria:** Framework compliance + code quality

## Context-Aware Selection

The context detector automatically selects presets based on:

| Change Size | Suggested Preset |
|-------------|------------------|
| < 50 lines | quick |
| 50-500 lines | thorough (or context-based) |
| > 500 lines | comprehensive |

| Detected Pattern | Added Agents |
|------------------|--------------|
| Test files | pr-review-toolkit:pr-test-analyzer |
| Type definitions | pr-review-toolkit:type-design-analyzer |
| Error handling | pr-review-toolkit:silent-failure-hunter |
