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

### Serialization

- Ensure `to_dict()` and `from_dict()` are symmetrical
- Don't mutate input dictionaries - use `.copy()`
- Validate required fields before construction

## Project Structure

- `scripts/` - Core Python modules (stdlib only)
- `schemas/` - Data structures and serialization
- `tests/` - Pytest test files
- `.claude/hookify.*.local.md` - Claude Code hook rules

## Key Invariants

1. Zero external dependencies in scripts
2. Backward compatibility for CLI interfaces
3. ExitCodes constants for all exit points
4. TYPE_CHECKING imports for forward references
