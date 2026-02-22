# Multi-Review Plugin - Project Conventions

## Code Style

### Exception Handling

- Use specific exception types in tests:
  ```python
  # Good
  pytest.raises(FrozenInstanceError)
  pytest.raises(ValueError)
  
  # Bad
  pytest.raises(Exception)  # Too broad
  ```

- Check SystemExit codes explicitly:
  ```python
  except SystemExit as e:
      if e.code == 0:
          return ExitCodes.SUCCESS  # --help, etc.
      return ExitCodes.INVALID_ARGS
  ```

### Logging

- Don't embed exceptions in `logger.exception()`:
  ```python
  # Good
  logger.exception("Failed to save calibration")
  
  # Bad
  logger.exception(f"Failed to save calibration: {e}")  # Redundant
  ```

### Path Management

- Check before inserting to sys.path:
  ```python
  scripts_path = str(Path(__file__).parent / "scripts")
  if scripts_path not in sys.path:
      sys.path.insert(0, scripts_path)
  ```

### Exit Codes

- Use `ExitCodes` constants from `utils.py`:
  - `ExitCodes.SUCCESS` (0)
  - `ExitCodes.FAILURE` (1)
  - `ExitCodes.INVALID_ARGS` (2)
  - `ExitCodes.CONFIG_ERROR` (3)
  - `ExitCodes.ERROR` (4)

### Linting

- Run `ruff check` before committing to catch issues:
  - Unused imports (F401)
  - Unused variables (F841)
  - f-strings without placeholders (F541)

### Serialization

- Ensure `to_dict()` and `from_dict()` are symmetrical
- Don't mutate input dictionaries - use `.copy()`
- Validate required fields before construction

## Project Structure

- `scripts/` - Core Python modules (stdlib only)
- `schemas/` - Data structures and serialization
- `tests/` - Pytest test files
- `.claude/hookify.*.local.md` - Claude Code hook rules

## Hookify Rules

Active hook rules in `.claude/`:

| Rule | Pattern | Description |
|------|---------|-------------|
| `warn-broad-exception` | `pytest.raises(Exception)` | Use specific exception types |
| `warn-systemexit-check` | `except SystemExit:` | Check exit code explicitly |
| `warn-logger-exception` | `logger.exception(f"...: {e}")` | Don't embed exception in message |
| `warn-sys-path-duplicate` | `sys.path.insert(0, ...)` | Check if path already exists |
| `warn-unused-fstring` | `lines.append(f"...")` | Use plain string if no interpolation |
| `warn-unused-variable` | `(context|results|...)\s*=\s*` | Remove unused assignments |

## Key Invariants

1. Zero external dependencies in scripts
2. Backward compatibility for CLIs
3. ExitCodes constants for all exit points
4. TYPE_CHECKING imports for forward references
