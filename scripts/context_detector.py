#!/usr/bin/env python3
"""
Multi-agent code review orchestration script.

This script provides context detection, agent suggestions, and result
aggregation for flexible multi-agent code reviews using the
Claude Code agent framework.

Dependencies:
    - git: Required for repository context detection
    - gh CLI: Optional, for PR-aware agent suggestions
    - Python 3.10+

Usage:
    python3 context_detector.py --suggest     # Context-aware suggestions
    python3 context_detector.py --list        # List all agents
    python3 context_detector.py --presets     # List available presets
    python3 context_detector.py --context     # Show detected context

Example:
    >>> context = detect_context()
    >>> agents = suggest_agents(context)
    >>> print(agents)
    ['feature-dev:code-reviewer', 'pr-review-toolkit:pr-test-analyzer']
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Change size thresholds for preset selection
CHANGE_SIZE_SMALL_THRESHOLD = 50   # Lines: use "quick" preset
CHANGE_SIZE_LARGE_THRESHOLD = 500  # Lines: use "comprehensive" preset

# Maximum reasonable change size (for bounds checking)
MAX_REASONABLE_CHANGE_SIZE = 10_000_000  # 10 million lines

# Default timeout for git/gh CLI operations (in seconds)
DEFAULT_GIT_TIMEOUT = 5
DEFAULT_GH_TIMEOUT = 5
VALIDATION_TIMEOUT = 2


# =============================================================================
# EXCEPTIONS
# =============================================================================

class EnvironmentValidationError(Exception):
    """Raised when environment validation fails.

    Attributes:
        errors: List of error messages describing validation failures.

    Example:
        >>> raise EnvironmentValidationError(["git not found", "gh CLI not found"])
    """

    def __init__(self, errors: List[str]):
        self.errors = errors
        message = "Environment validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        super().__init__(message)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _run_git_command(
    args: List[str],
    timeout: int = DEFAULT_GIT_TIMEOUT,
    operation: str = "git command"
) -> subprocess.CompletedProcess:
    """Run a git command with comprehensive error handling.

    Args:
        args: Command arguments (without 'git' prefix).
        timeout: Timeout in seconds (default: 5).
        operation: Human-readable operation name for error messages.

    Returns:
        CompletedProcess result with stdout, stderr, returncode.

    Raises:
        RuntimeError: With actionable error message on failure.
        FileNotFoundError: If git executable not found.
        subprocess.TimeoutExpired: If command times out.
        PermissionError: If permission denied.
        OSError: For other OS-level errors.

    Example:
        >>> result = _run_git_command(["diff", "--cached", "--name-only"])
        >>> files = result.stdout.strip().split("\\n") if result.stdout.strip() else []
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
        )

        # Check for specific git errors
        if result.returncode != 0:
            stderr = result.stderr.strip()

            # Provide actionable error messages
            if "index.lock" in stderr.lower() or "locked" in stderr.lower():
                raise RuntimeError(
                    f"{operation} failed: Git index is locked. "
                    f"Another git operation may be in progress. "
                    f"Try closing other git terminals or remove .git/index.lock"
                )
            elif "corrupt" in stderr.lower():
                raise RuntimeError(
                    f"{operation} failed: Git repository may be corrupted. "
                    f"Run 'git fsck' to diagnose."
                )
            elif "not a git repository" in stderr.lower():
                raise RuntimeError(
                    f"{operation} failed: Not in a git repository"
                )
            elif "fatal:" in stderr.lower():
                raise RuntimeError(
                    f"{operation} failed: {stderr or 'unknown error'}"
                )

        return result

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"{operation} timed out after {timeout} seconds. "
            f"Repository may be very large or git may be unresponsive."
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"{operation} failed: git executable not found. "
            f"Install from https://git-scm.com/"
        )
    except PermissionError as e:
        raise RuntimeError(
            f"{operation} failed: Permission denied: {e}"
        )
    except OSError as e:
        raise RuntimeError(
            f"{operation} failed: {e}"
        )
    # Don't catch Exception here - let specific errors propagate


def _run_gh_command(
    args: List[str],
    timeout: int = DEFAULT_GH_TIMEOUT
) -> subprocess.CompletedProcess:
    """Run a GitHub CLI (gh) command with comprehensive error handling.

    Args:
        args: Command arguments (without 'gh' prefix).
        timeout: Timeout in seconds (default: 5).

    Returns:
        CompletedProcess result with stdout, stderr, returncode.

    Raises:
        RuntimeError: With actionable error message on failure.
        FileNotFoundError: If gh CLI not found.
        subprocess.TimeoutExpired: If command times out.

    Notes:
        - gh CLI is optional; PR detection will be skipped if not available.
        - Returns result with returncode set; caller should check for success.

    Example:
        >>> result = _run_gh_command(["pr", "view", "--json", "state"])
        >>> has_pr = result.returncode == 0
    """
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
        )
        return result

    except FileNotFoundError:
        raise RuntimeError(
            "gh CLI not found. Install from https://cli.github.com/ "
            "to enable PR-aware agent suggestions."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"gh command timed out after {timeout} seconds. "
            "Check network connectivity."
        )
    except OSError as e:
        raise RuntimeError(
            f"gh command failed: {e}"
        )


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass(frozen=True)
class Agent:
    """Agent definition for multi-agent code review.

    Attributes:
        name: Full qualified agent name in 'namespace:agent-name' format.
        description: Human-readable description of the agent's purpose.
        source: Plugin source ('feature-dev', 'pr-review-toolkit', or 'superpowers').

    Example:
        >>> agent = Agent("feature-dev:code-reviewer", "General review", "feature-dev")
        >>> agent.name
        'feature-dev:code-reviewer'
    """
    name: str
    description: str
    source: str  # "feature-dev", "pr-review-toolkit", "superpowers"

    def __post_init__(self) -> None:
        """Validate agent data after initialization.

        Raises:
            ValueError: If name format is invalid or source is not recognized.
        """
        # Validate agent name format
        _validate_agent_name(self.name)

        # Validate source is one of the recognized values
        valid_sources = {"feature-dev", "pr-review-toolkit", "superpowers"}
        if self.source not in valid_sources:
            raise ValueError(
                f"Invalid agent source '{self.source}'. "
                f"Must be one of: {', '.join(sorted(valid_sources))}"
            )


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def _validate_agent_name(agent_name: str) -> None:
    """Validate agent name follows namespace:agent-name format.

    Args:
        agent_name: Agent name to validate.

    Raises:
        ValueError: If agent name doesn't match expected format.
    """
    if not agent_name:
        raise ValueError("Agent name cannot be empty")

    # Strip whitespace and validate no remaining whitespace
    agent_name_stripped = agent_name.strip()
    if agent_name != agent_name_stripped:
        raise ValueError(
            f"Agent name '{agent_name}' has leading/trailing whitespace. "
            f"Use '{agent_name_stripped}' instead."
        )

    if " " in agent_name or "\t" in agent_name:
        raise ValueError(
            f"Agent name '{agent_name}' contains whitespace. "
            f"Use format 'namespace:agent-name' without spaces."
        )

    # Check for control characters and other problematic characters
    problematic_chars = ['\n', '\r', '\0', '\v', '\f']
    found = [c for c in problematic_chars if c in agent_name]
    if found:
        raise ValueError(
            f"Agent name '{agent_name}' contains invalid character(s): {repr(found)}"
        )

    parts = agent_name.split(":")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid agent name format '{agent_name}'. "
            f"Expected 'namespace:agent-name' format with exactly one colon separator."
        )

    namespace, name = parts
    if not namespace or not name:
        raise ValueError(
            f"Invalid agent name '{agent_name}'. "
            f"Both namespace and agent name must be non-empty."
        )


def _validate_agent_data_consistency() -> None:
    """Validate that all agents in AGENT_PRESETS exist in AGENT_MAP.

    Also checks for duplicates and other inconsistencies.

    Raises:
        ValueError: If data consistency issues are detected.
    """
    errors = []

    # Check 1: Agents in presets exist in map
    missing_agents = []
    for preset_name, agent_list in AGENT_PRESETS.items():
        for agent_name in agent_list:
            if agent_name not in AGENT_MAP:
                missing_agents.append(
                    f"  - '{agent_name}' in preset '{preset_name}'"
                )

    if missing_agents:
        errors.append(
            "Agents in AGENT_PRESETS not found in AGENT_MAP:\n"
            + "\n".join(missing_agents) +
            f"\n\nAvailable agents in AGENT_MAP: {list(AGENT_MAP.keys())}"
        )

    # Check 2: No duplicate agents in presets
    for preset_name, agent_list in AGENT_PRESETS.items():
        seen: set[str] = set()
        duplicates: set[str] = set()
        for agent_name in agent_list:
            if agent_name in seen:
                duplicates.add(agent_name)
            seen.add(agent_name)

        if duplicates:
            errors.append(
                f"Duplicate agents in preset '{preset_name}': {list(duplicates)}"
            )

    # Check 3: No duplicate agent names in AGENT_MAP
    agent_names = list(AGENT_MAP.keys())
    if len(agent_names) != len(set(agent_names)):
        map_seen: dict[str, int] = {}
        map_duplicates: list[str] = []
        for name in agent_names:
            if name in map_seen:
                map_duplicates.append(f"'{name}' appears {map_seen[name] + 1} times")
            map_seen[name] = map_seen.get(name, 0) + 1

        if map_duplicates:
            errors.append(f"Duplicate agent names in AGENT_MAP: {map_duplicates}")

    # Check 4: Validate all agent name formats
    for agent_name in AGENT_MAP.keys():
        try:
            _validate_agent_name(agent_name)
        except ValueError as e:
            errors.append(f"Invalid agent name '{agent_name}': {e}")

    if errors:
        error_msg = "Data consistency errors detected:\n\n" + "\n\n".join(errors)
        logger.critical(error_msg)
        raise ValueError(error_msg)


# =============================================================================
# AGENT DATA
# =============================================================================

# Available agents organized by priority
PRIMARY_AGENTS = [
    Agent("feature-dev:code-reviewer", "General code review with confidence scoring", "feature-dev"),
]

SPECIALIZED_AGENTS = [
    Agent("pr-review-toolkit:pr-test-analyzer", "Test coverage quality and completeness", "pr-review-toolkit"),
    Agent("pr-review-toolkit:silent-failure-hunter", "Error handling and silent failures", "pr-review-toolkit"),
    Agent("pr-review-toolkit:type-design-analyzer", "Type design quality and invariants", "pr-review-toolkit"),
    Agent("pr-review-toolkit:comment-analyzer", "Code comment accuracy and maintainability", "pr-review-toolkit"),
    Agent("pr-review-toolkit:code-simplifier", "Code simplification and refactoring", "pr-review-toolkit"),
    Agent("pr-review-toolkit:code-reviewer", "General code review for project guidelines", "pr-review-toolkit"),
]

FRAMEWORK_AGENTS = [
    Agent("superpowers:code-review-checklist", "Framework-specific review guidance", "superpowers"),
]

ALL_AGENTS = PRIMARY_AGENTS + SPECIALIZED_AGENTS + FRAMEWORK_AGENTS
AGENT_MAP = {agent.name: agent for agent in ALL_AGENTS}

# Agent presets with full qualified names
AGENT_PRESETS = {
    "quick": [
        "feature-dev:code-reviewer",
        "pr-review-toolkit:code-simplifier",
    ],
    "thorough": [
        "feature-dev:code-reviewer",
        "pr-review-toolkit:pr-test-analyzer",
        "pr-review-toolkit:silent-failure-hunter",
        "pr-review-toolkit:code-simplifier",
    ],
    "comprehensive": [
        "feature-dev:code-reviewer",
        "pr-review-toolkit:pr-test-analyzer",
        "pr-review-toolkit:silent-failure-hunter",
        "pr-review-toolkit:type-design-analyzer",
        "pr-review-toolkit:comment-analyzer",
        "pr-review-toolkit:code-simplifier",
        "pr-review-toolkit:code-reviewer",
    ],
    "framework": ["superpowers:code-review-checklist"],
}


# =============================================================================
# LAZY VALIDATION
# =============================================================================

_validation_performed = False
_validation_failed = False


def _ensure_agent_data_consistency() -> None:
    """Ensure agent data is consistent, validating once.

    Raises:
        ValueError: If data consistency issues are detected.
    """
    global _validation_performed, _validation_failed

    if _validation_performed:
        if _validation_failed:
            raise ValueError("Agent data consistency check previously failed")
        return

    try:
        _validate_agent_data_consistency()
        _validation_performed = True
    except ValueError:
        _validation_failed = True
        raise


# =============================================================================
# CONTEXT DETECTION
# =============================================================================

def detect_context() -> Dict[str, Any]:
    """Detect repository context and state.

    Performs git and gh CLI operations to gather:
    - PR status (via gh CLI)
    - Changed files (staged + working directory)
    - File type patterns (tests, types, error handlers)
    - Change size (line count from git diff --shortstat)

    Returns:
        Dictionary with keys: has_pr, has_tests, has_types, has_error_handling,
        has_comments, change_size, staged_files, working_files.
        May include partial_context=True if git detection failed partially.

    Notes:
        - Logs warnings for non-fatal errors (gh CLI not found, git timeout)
        - Returns partial context on git failures (fields may be empty/default)
        - Change size of 0 indicates detection failure or no changes

    Raises:
        RuntimeError: If git binary not found and no context can be detected.
    """
    context: Dict[str, Any] = {
        "has_pr": False,
        "has_tests": False,
        "has_types": False,
        "has_error_handling": False,
        "has_comments": False,
        "change_size": 0,
        "staged_files": [],
        "working_files": [],
    }

    # Detect PR using helper
    try:
        result = _run_gh_command(["pr", "view", "--json", "state"])
        context["has_pr"] = result.returncode == 0

        # If gh CLI exists but returns error, provide helpful feedback
        if result.returncode != 0 and result.stderr:
            if "not logged in" in result.stderr.lower():
                logger.warning(
                    "gh CLI not authenticated. Run 'gh auth login' to enable PR detection."
                )
            elif "not a git repository" in result.stderr.lower():
                logger.debug("Not in a git repository - PR detection unavailable")
            elif "could not find a pr" in result.stderr.lower():
                logger.debug("No PR found for current branch")

    except RuntimeError as e:
        # RuntimeError from _run_gh_command already has actionable message
        logger.warning(str(e))
        context["has_pr"] = False

    # Detect git state
    try:
        # Detect staged files using helper
        result = _run_git_command(
            ["diff", "--cached", "--name-only"],
            operation="staged files detection"
        )
        if result.stdout.strip():
            # Sanitize file paths (filter null bytes, carriage returns)
            raw_files = result.stdout.strip().split("\n")
            context["staged_files"] = [
                f for f in raw_files
                if f and not any(c in f for c in ['\0', '\r'])
            ]

        # Detect working directory files using helper
        result = _run_git_command(
            ["diff", "--name-only"],
            operation="working directory detection"
        )
        if result.stdout.strip():
            raw_files = result.stdout.strip().split("\n")
            context["working_files"] = [
                f for f in raw_files
                if f and not any(c in f for c in ['\0', '\r'])
            ]

        # Combine all changed files
        all_files = context["staged_files"] + context["working_files"]

        # Check for test files (case-insensitive)
        test_patterns = ["_test.py", "_test.ts", ".test.ts", ".spec.ts", "__tests__.py", "tests/"]
        context["has_tests"] = any(
            any(pattern.lower() in f.lower() for pattern in test_patterns)
            for f in all_files
        )

        # Check for type definitions (case-insensitive)
        type_patterns = ["_types.ts", ".d.ts", "types.py", "types.ts"]
        context["has_types"] = any(
            any(pattern.lower() in f.lower() for pattern in type_patterns)
            for f in all_files
        )

        # Check for error handling changes (case-insensitive)
        error_patterns = ["error", "exception", "handler"]
        context["has_error_handling"] = any(
            any(pattern.lower() in f.lower() for pattern in error_patterns)
            for f in all_files
        )

        # Estimate change size with robust parsing using helper
        result = _run_git_command(
            ["diff", "--cached", "--shortstat"],
            operation="change size detection"
        )
        if result.stdout.strip():
            try:
                # More robust parsing using regex
                match = re.search(r'(\d+)\s+insertion', result.stdout)
                if match:
                    change_size = int(match.group(1))
                    # Add bounds checking
                    context["change_size"] = min(change_size, MAX_REASONABLE_CHANGE_SIZE)
                    if change_size >= MAX_REASONABLE_CHANGE_SIZE:
                        logger.warning(f"Change size capped at {MAX_REASONABLE_CHANGE_SIZE}")
            except (ValueError, AttributeError) as e:
                logger.error(
                    f"Unexpected error parsing git shortstat output: {e}. "
                    f"Output was: {result.stdout}"
                )

    except RuntimeError as e:
        # RuntimeError from _run_git_command - already has actionable message
        logger.error(f"Git context detection failed: {e}")
        context["partial_context"] = True

    return context


# =============================================================================
# PROJECT CONTEXT DETECTION (3-Layer Defense - Layer 1)
# =============================================================================

def detect_pyproject_config(repo_root: Path) -> Dict[str, Any]:
    """Parse pyproject.toml for Python tool configuration.

    Extracts configuration from [tool.mypy], [tool.ruff], and related sections.
    This is FACT evidence - directly parsed from config files.

    Args:
        repo_root: Path to the repository root.

    Returns:
        Dictionary with keys:
            - mypy_strict: bool (from mypy.strict or mypy.strict_optional)
            - mypy_configured: bool (whether [tool.mypy] exists)
            - ruff_rules: list[str] of enabled rules
            - type_checking_level: str ("strict", "moderate", "relaxed", "none")

    Example:
        >>> config = detect_pyproject_config(Path.cwd())
        >>> config["mypy_strict"]
        True
    """
    result = {
        "mypy_strict": False,
        "mypy_configured": False,
        "ruff_rules": [],
        "type_checking_level": "none",
    }

    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        return result

    try:
        content = pyproject_path.read_text(encoding='utf-8')

        # Simple TOML parsing without external dependencies
        # Look for [tool.mypy] section
        in_mypy_section = False
        in_ruff_section = False

        for line in content.split('\n'):
            line = line.strip()

            # Section detection
            if line == "[tool.mypy]":
                in_mypy_section = True
                in_ruff_section = False
                result["mypy_configured"] = True
                continue
            elif line == "[tool.ruff]":
                in_ruff_section = True
                in_mypy_section = False
                continue
            elif line.startswith("[") and line != "[tool.mypy]" and line != "[tool.ruff]":
                in_mypy_section = False
                in_ruff_section = False
                continue

            # Parse mypy config
            if in_mypy_section:
                if "strict" in line.lower() and "=" in line:
                    # Check if strict mode is enabled
                    if "true" in line.lower() or "yes" in line.lower():
                        result["mypy_strict"] = True
                        result["type_checking_level"] = "strict"
                elif ("strict_optional" in line.lower() or
                      "disallow_untyped_defs" in line.lower() or
                      "warn_return_any" in line.lower()):
                    if "true" in line.lower() or "yes" in line.lower():
                        result["mypy_strict"] = True
                        if result["type_checking_level"] == "none":
                            result["type_checking_level"] = "moderate"

            # Parse ruff config (look for select rules)
            if in_ruff_section:
                if "select" in line.lower() and "=" in line:
                    # Extract rule codes like ["E", "F", "I"]
                    import re
                    rules_match = re.findall(r'"([A-Z]+)"', line)
                    result["ruff_rules"].extend(rules_match)

        # Deduplicate ruff rules
        result["ruff_rules"] = sorted(set(result["ruff_rules"]))

        # Infer type checking level if not set
        if result["type_checking_level"] == "none" and result["mypy_configured"]:
            result["type_checking_level"] = "relaxed"

    except (OSError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to parse pyproject.toml: {e}")

    return result


def detect_ruff_config(repo_root: Path) -> List[str]:
    """Parse ruff.toml or .ruff.toml for enabled rules.

    Args:
        repo_root: Path to the repository root.

    Returns:
        List of enabled ruff rule codes.
    """
    rules = []

    for config_file in ["ruff.toml", ".ruff.toml"]:
        config_path = repo_root / config_file
        if not config_path.exists():
            continue

        try:
            content = config_path.read_text(encoding='utf-8')
            import re
            # Look for select = [...] or extend-select = [...]
            for line in content.split('\n'):
                if "select" in line.lower() and "=" in line:
                    rules_match = re.findall(r'"([A-Z]+)"', line)
                    rules.extend(rules_match)
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to parse {config_file}: {e}")

    return sorted(set(rules))


def detect_mypy_config(repo_root: Path) -> Dict[str, bool]:
    """Parse mypy.ini or setup.cfg for mypy configuration.

    Args:
        repo_root: Path to the repository root.

    Returns:
        Dictionary with mypy configuration flags.
    """
    result = {"strict": False, "configured": False}

    # Check mypy.ini
    mypy_ini = repo_root / "mypy.ini"
    setup_cfg = repo_root / "setup.cfg"

    for config_path in [mypy_ini, setup_cfg]:
        if not config_path.exists():
            continue

        try:
            content = config_path.read_text(encoding='utf-8')
            in_mypy_section = False

            for line in content.split('\n'):
                line = line.strip()

                if config_path.name == "mypy.ini":
                    if line == "[mypy]" or line.startswith("[mypy-"):
                        in_mypy_section = True
                        result["configured"] = True
                        continue
                else:  # setup.cfg
                    if line == "[mypy]":
                        in_mypy_section = True
                        result["configured"] = True
                        continue

                if line.startswith("[") and not line.startswith("[mypy"):
                    in_mypy_section = False
                    continue

                if in_mypy_section:
                    if "strict" in line.lower() and "=" in line:
                        if "true" in line.lower() or "yes" in line.lower():
                            result["strict"] = True
                    elif any(flag in line.lower() for flag in [
                        "strict_optional", "disallow_untyped_defs",
                        "warn_return_any", "disallow_any_generics"
                    ]):
                        if "true" in line.lower() or "yes" in line.lower():
                            result["strict"] = True

        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to parse {config_path.name}: {e}")

    return result


def detect_shell_strict_mode(files: List[str], repo_root: Path) -> Dict[str, Any]:
    """Detect shell scripts with strict mode enabled.

    Searches for `set -euo pipefail` or equivalent patterns in shell files.
    This is FACT evidence - directly parsed from file contents.

    Args:
        files: List of file paths to check (relative to repo_root).
        repo_root: Path to the repository root.

    Returns:
        Dictionary with keys:
            - strict_mode_files: set of Path objects with strict mode
            - detection_evidence: list of "filepath:line" strings
            - has_any_shell_scripts: bool

    Example:
        >>> result = detect_shell_strict_mode(["script.sh"], Path.cwd())
        >>> result["strict_mode_files"]
        {Path('script.sh')}
    """
    result = {
        "strict_mode_files": set(),
        "detection_evidence": [],
        "has_any_shell_scripts": False,
    }

    shell_extensions = {'.sh', '.bash', '.zsh'}
    strict_patterns = [
        'set -euo pipefail',
        'set -e -u -o pipefail',
        'set -eo pipefail',
        'set -eu pipefail',
    ]

    for file_path in files:
        # Check if it's a shell script
        path = Path(file_path)
        if path.suffix not in shell_extensions:
            continue

        result["has_any_shell_scripts"] = True
        full_path = repo_root / file_path

        try:
            content = full_path.read_text(encoding='utf-8', errors='replace')
            for i, line in enumerate(content.split('\n'), 1):
                # Check for strict mode patterns
                line_stripped = line.strip()
                if any(pattern in line_stripped for pattern in strict_patterns):
                    result["strict_mode_files"].add(Path(file_path))
                    result["detection_evidence"].append(f"{file_path}:{i}:{line_stripped[:50]}")
                    break  # Only record first occurrence per file
        except (OSError, PermissionError) as e:
            logger.debug(f"Could not read shell file {file_path}: {e}")

    return result


def detect_result_pattern(repo_root: Path, files: List[str]) -> Dict[str, Any]:
    """Detect if the project uses Result/Either pattern for error handling.

    This is HEURISTIC evidence - inferred from import patterns.
    The evidence field contains the actual lines that triggered detection.

    Args:
        repo_root: Path to the repository root.
        files: List of Python files to check.

    Returns:
        Dictionary with keys:
            - uses_result_pattern: bool
            - evidence: list of strings showing detected imports

    Example:
        >>> result = detect_result_pattern(Path.cwd(), ["src/main.py"])
        >>> result["uses_result_pattern"]
        True
        >>> result["evidence"]
        ["src/main.py:from returns.result import Result"]
    """
    result = {
        "uses_result_pattern": False,
        "evidence": [],
    }

    result_patterns = [
        'from returns.result import',
        'from returns import Result',
        'from result import Result',
        'from either import Either',
        'from pydantic import Result',
        'import returns',
    ]

    python_files = [f for f in files if f.endswith('.py')]

    for file_path in python_files[:50]:  # Limit to first 50 files for performance
        full_path = repo_root / file_path
        try:
            content = full_path.read_text(encoding='utf-8', errors='replace')
            for i, line in enumerate(content.split('\n'), 1):
                line_stripped = line.strip()
                for pattern in result_patterns:
                    if pattern in line_stripped:
                        result["uses_result_pattern"] = True
                        result["evidence"].append(f"{file_path}:{i}:{line_stripped[:60]}")
                        break
        except (OSError, PermissionError):
            pass

    return result


def get_git_blame_authors(files: List[str], repo_root: Path) -> Dict[str, List[str]]:
    """Get authors of lines in changed files via git blame.

    This helps identify pre-existing issues (lines written by others).

    Args:
        files: List of file paths to blame.
        repo_root: Path to the repository root.

    Returns:
        Dictionary mapping file paths to lists of author names.

    Note:
        Returns empty dict if git blame fails or is unavailable.
    """
    result = {}

    for file_path in files[:20]:  # Limit for performance
        try:
            blame_result = _run_git_command(
                ["blame", "--line-porcelain", file_path],
                timeout=10,
                operation=f"git blame for {file_path}"
            )

            if blame_result.returncode == 0:
                authors = set()
                for line in blame_result.stdout.split('\n'):
                    if line.startswith('author '):
                        author = line[7:].strip()
                        if author and author != 'Not Committed Yet':
                            authors.add(author)
                result[file_path] = list(authors)
        except RuntimeError as e:
            logger.debug(f"Could not blame {file_path}: {e}")

    return result


def build_project_context(
    repo_root: Optional[Path] = None,
    changed_files: Optional[List[str]] = None
) -> "ProjectContext":
    """Build complete ProjectContext for false positive elimination.

    This is the unified entry point that combines all context detection.
    It coordinates detection of Python config, shell config, test config,
    and git metadata into a single ProjectContext object.

    Args:
        repo_root: Path to repository root (defaults to cwd).
        changed_files: List of changed files (defaults to git detection).

    Returns:
        ProjectContext with all configuration populated.

    Example:
        >>> context = build_project_context()
        >>> context.python_config.mypy_strict.value
        True
        >>> context.to_context_hash()
        'a1b2c3d4...'
    """
    from project_context import (
        ConfigValue,
        EvidenceLevel,
        GitMetadata,
        ProjectContext,
        PythonConfig,
        ShellConfig,
        TestConfig,
    )

    if repo_root is None:
        repo_root = Path.cwd()

    # Get changed files from git if not provided
    if changed_files is None:
        try:
            staged_result = _run_git_command(
                ["diff", "--cached", "--name-only"],
                operation="get staged files"
            )
            working_result = _run_git_command(
                ["diff", "--name-only"],
                operation="get working files"
            )
            staged = staged_result.stdout.strip().split('\n') if staged_result.stdout.strip() else []
            working = working_result.stdout.strip().split('\n') if working_result.stdout.strip() else []
            changed_files = [f for f in staged + working if f]
        except RuntimeError:
            changed_files = []

    # Detect Python configuration
    pyproject_config = detect_pyproject_config(repo_root)
    ruff_rules = detect_ruff_config(repo_root)
    mypy_config = detect_mypy_config(repo_root)

    # Combine mypy config from all sources
    mypy_strict = pyproject_config["mypy_strict"] or mypy_config["strict"]
    mypy_configured = pyproject_config["mypy_configured"] or mypy_config["configured"]
    all_ruff_rules = sorted(set(pyproject_config["ruff_rules"] + ruff_rules))

    # Detect Result pattern
    result_pattern = detect_result_pattern(repo_root, changed_files)

    # Detect shell strict mode
    shell_config = detect_shell_strict_mode(changed_files, repo_root)

    # Build PythonConfig
    python_config = PythonConfig(
        mypy_strict=ConfigValue(
            mypy_strict,
            EvidenceLevel.FACT if mypy_configured else EvidenceLevel.ASSUMPTION,
            "pyproject.toml [tool.mypy] or mypy.ini" if mypy_configured else "no mypy config found"
        ),
        mypy_configured=ConfigValue(
            mypy_configured,
            EvidenceLevel.FACT,
            "config file present" if mypy_configured else "no config file"
        ),
        ruff_rules=frozenset(all_ruff_rules),
        type_checking_level=ConfigValue(
            pyproject_config["type_checking_level"],
            EvidenceLevel.FACT if mypy_configured else EvidenceLevel.ASSUMPTION,
            "from mypy config" if mypy_configured else "no type checker configured"
        ),
        uses_result_pattern=ConfigValue(
            result_pattern["uses_result_pattern"],
            EvidenceLevel.HEURISTIC if result_pattern["uses_result_pattern"] else EvidenceLevel.ASSUMPTION,
            "detected Result imports" if result_pattern["uses_result_pattern"] else "no Result imports detected"
        ),
        result_pattern_evidence=frozenset(result_pattern["evidence"]),
    )

    # Build ShellConfig
    shell_cfg = ShellConfig(
        strict_mode_files=frozenset(shell_config["strict_mode_files"]),
        detection_evidence=frozenset(shell_config["detection_evidence"]),
        has_any_shell_scripts=ConfigValue(
            shell_config["has_any_shell_scripts"],
            EvidenceLevel.FACT,
            "shell file extensions detected" if shell_config["has_any_shell_scripts"] else "no shell files found"
        ),
    )

    # Build TestConfig
    test_patterns = ["_test.py", "_tests.py", "test_", "tests/", "conftest.py"]
    has_tests = any(
        any(pattern in f for pattern in test_patterns)
        for f in changed_files
    )

    test_framework = "none"
    if has_tests:
        # Simple heuristic for test framework detection
        test_framework = "pytest"  # Most common assumption

    test_cfg = TestConfig(
        has_tests=ConfigValue(
            has_tests,
            EvidenceLevel.FACT if has_tests else EvidenceLevel.ASSUMPTION,
            "test files detected" if has_tests else "no test files found"
        ),
        test_framework=ConfigValue(
            test_framework,
            EvidenceLevel.HEURISTIC if has_tests else EvidenceLevel.ASSUMPTION,
            "inferred from file naming" if has_tests else "no test framework detected"
        ),
        coverage_tool=ConfigValue(
            "none",
            EvidenceLevel.ASSUMPTION,
            "no coverage tool configured"
        ),
        min_coverage_threshold=ConfigValue(
            None,
            EvidenceLevel.ASSUMPTION,
            "no coverage threshold configured"
        ),
    )

    # Build GitMetadata
    has_git = (repo_root / ".git").exists()
    git_meta = GitMetadata(
        has_git=ConfigValue(
            has_git,
            EvidenceLevel.FACT,
            ".git directory present" if has_git else "not a git repository"
        ),
        main_branch=ConfigValue(
            "main",
            EvidenceLevel.ASSUMPTION,
            "default assumption"
        ),
        pre_existing_issue_authors=frozenset(),
        changed_files=frozenset(changed_files),
    )

    return ProjectContext(
        python_config=python_config,
        shell_config=shell_cfg,
        test_config=test_cfg,
        git_metadata=git_meta,
    )


# =============================================================================
# ENVIRONMENT VALIDATION
# =============================================================================

def validate_environment(raise_on_error: bool = False) -> Tuple[bool, List[str]]:
    """Validate that required tools are available.

    Checks for git (required) and gh CLI (optional) availability.

    Args:
        raise_on_error: If True, raises EnvironmentValidationError on failure.
            If False, returns tuple for backward compatibility.

    Returns:
        Tuple of (is_valid: bool, errors: list[str]) when raise_on_error=False.
        When raise_on_error=True, raises EnvironmentValidationError instead.

    Raises:
        EnvironmentValidationError: If validation fails and raise_on_error=True.

    Examples:
        >>> is_valid, errors = validate_environment()
        >>> if not is_valid:
        ...     print("\\n".join(errors))
    """
    errors = []

    # Check git (REQUIRED)
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=VALIDATION_TIMEOUT,
        )
        if result.returncode != 0:
            error = "git is not working properly"
            errors.append(error)
            logger.error(error)
        elif not result.stdout.strip():
            error = "git produced no output (may be corrupted)"
            errors.append(error)
            logger.error(error)
        else:
            logger.info(f"git detected: {result.stdout.strip()}")

    except FileNotFoundError:
        error = "git not found - install from https://git-scm.com/"
        errors.append(error)
        logger.error(error)
    except subprocess.TimeoutExpired:
        error = "git timed out after 2 seconds - may not be responding"
        errors.append(error)
        logger.error(error)
    except PermissionError as e:
        error = f"git permission denied: {e}"
        errors.append(error)
        logger.error(error)
    # Catch-all for truly unexpected exceptions (defensive programming at top level).
    # This is acceptable here because: (1) we're at module entry point, (2) we log
    # the full traceback for debugging, (3) we return error status rather than crash.
    except Exception as e:
        error = f"Unexpected git check failure: {e}"
        errors.append(error)
        logger.error(error, exc_info=True)

    # Check gh CLI (OPTIONAL)
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=VALIDATION_TIMEOUT,
        )
        if result.returncode == 0:
            logger.info(f"gh CLI detected: {result.stdout.strip()}")
        else:
            logger.debug("gh CLI check returned non-zero (optional tool)")
    except FileNotFoundError:
        logger.debug("gh CLI not found - PR detection will be disabled")
    except subprocess.TimeoutExpired:
        logger.debug("gh CLI timed out (optional tool)")
    # Catch-all for truly unexpected exceptions (gh CLI is optional, so we
    # log and continue rather than crash)
    except Exception as e:
        logger.debug(f"gh CLI check failed: {e}")

    is_valid = len(errors) == 0

    if not is_valid and raise_on_error:
        raise EnvironmentValidationError(errors)

    return is_valid, errors


# =============================================================================
# AGENT SELECTION
# =============================================================================

def _find_agent(preset: str, suffix: str) -> str:
    """Find agent in preset by name suffix.

    Searches for agents ending with the given suffix within a preset.
    Validates agent name format and existence in AGENT_MAP.

    Args:
        preset: Preset name ('thorough', 'comprehensive', etc.)
        suffix: Agent name suffix ('pr-test-analyzer', 'code-reviewer', etc.)

    Returns:
        Full qualified agent name with namespace prefix.

    Raises:
        ValueError: If suffix is empty, preset is invalid, no match found,
            match is ambiguous, agent format invalid, or agent not in AGENT_MAP.

    Example:
        >>> _find_agent("thorough", "pr-test-analyzer")
        'pr-review-toolkit:pr-test-analyzer'
    """
    if not suffix:
        raise ValueError("suffix cannot be empty")

    if preset not in AGENT_PRESETS:
        raise ValueError(f"Invalid preset '{preset}'. Must be one of: {list(AGENT_PRESETS.keys())}")

    # Find all agents matching the suffix
    matching_agents = [agent for agent in AGENT_PRESETS[preset] if agent.endswith(suffix)]

    if not matching_agents:
        raise ValueError(f"No agent ending with '{suffix}' in {preset} preset")

    # Check for ambiguous matches
    if len(matching_agents) > 1:
        raise ValueError(
            f"Ambiguous suffix '{suffix}' in {preset} preset. "
            f"Multiple agents match: {matching_agents}"
        )

    agent = matching_agents[0]

    # Validate agent name format
    _validate_agent_name(agent)

    # Check agent exists in AGENT_MAP
    if agent not in AGENT_MAP:
        raise ValueError(
            f"Agent '{agent}' found in preset '{preset}' but not in AGENT_MAP. "
            f"Available agents: {list(AGENT_MAP.keys())}"
        )

    return agent


def _get_preset_reason(preset: str, context: Dict[str, Any]) -> str:
    """Generate explanation for why a preset was suggested.

    Args:
        preset: Preset name that was selected.
        context: Repository context from detect_context().

    Returns:
        Human-readable explanation string.
    """
    reasons = {
        "quick": "Small change (< 50 lines) - fast review",
        "thorough": "Medium change with specific focus areas",
        "comprehensive": "Large change (> 500 lines) - complete review",
        "framework": "Framework-specific compliance review",
    }

    base_reason = reasons.get(preset, "Standard review")

    # Add context-specific details
    details = []
    if context.get("has_tests"):
        details.append("test files detected")
    if context.get("has_types"):
        details.append("type definitions detected")
    if context.get("has_error_handling"):
        details.append("error handling changes detected")

    if details:
        return f"{base_reason} ({', '.join(details)})"
    return base_reason


def format_output(context: Dict[str, Any], suggested_preset: str, warnings: List[str]) -> str:
    """Format detection results as structured JSON.

    Args:
        context: Detected repository context.
        suggested_preset: Recommended preset name.
        warnings: List of non-fatal warnings.

    Returns:
        JSON string with structured output.
    """
    output = {
        "success": True,
        "context": context,
        "suggested_preset": suggested_preset,
        "suggested_reason": _get_preset_reason(suggested_preset, context),
        "available_agents": AGENT_PRESETS.get(suggested_preset, []),
        "warnings": warnings,
        "errors": [],
    }
    return json.dumps(output, indent=2)


def suggest_agents(context: Dict[str, Any]) -> List[str]:
    """Suggest agents based on repository context.

    Uses change size and file type detection to recommend appropriate
    review agents from AGENT_PRESETS.

    Args:
        context: Repository context from detect_context() with keys:
            - change_size: Number of lines changed (int)
            - has_tests: Whether test files were detected (bool)
            - has_types: Whether type definition files detected (bool)
            - has_error_handling: Whether error handler files detected (bool)

    Returns:
        List of full qualified agent names with namespace prefixes.

    Selection Criteria:
        - change_size < 50: Returns 'quick' preset (1 agent)
        - change_size > 500: Returns 'comprehensive' preset (7 agents)
        - Medium changes: Builds custom list based on detected file types

    Example:
        >>> context = {"change_size": 100, "has_tests": True}
        >>> suggest_agents(context)
        ['feature-dev:code-reviewer', 'pr-review-toolkit:pr-test-analyzer']
    """
    # Size-based preset selection using constants
    if context.get("change_size", 0) < CHANGE_SIZE_SMALL_THRESHOLD:
        return AGENT_PRESETS["quick"]
    elif context.get("change_size", 0) > CHANGE_SIZE_LARGE_THRESHOLD:
        return AGENT_PRESETS["comprehensive"]

    # Medium-sized changes - build custom list based on context
    agents = [_find_agent("quick", "code-reviewer")]

    if context.get("has_tests", False):
        agents.append(_find_agent("thorough", "pr-test-analyzer"))

    if context.get("has_types", False):
        agents.append(_find_agent("comprehensive", "type-design-analyzer"))

    if context.get("has_error_handling", False):
        agents.append(_find_agent("thorough", "silent-failure-hunter"))

    return agents


def format_agent_list(agents: List[Agent], group_name: str) -> str:
    """Format agents for display.

    Args:
        agents: List of Agent objects to format.
        group_name: Section header for the agent group.

    Returns:
        Formatted string with group name and agent details.

    Example:
        >>> agents = [Agent("feature-dev:code-reviewer", "General review", "feature-dev")]
        >>> print(format_agent_list(agents, "Primary"))
        <blank line>
        Primary:
          feature-dev:code-reviewer: General code review with confidence scoring
    """
    lines = [f"\n{group_name}:"]
    for agent in agents:
        lines.append(f"  {agent.name}: {agent.description}")
    return "\n".join(lines)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> None:
    """Main entry point with comprehensive error handling."""
    try:
        # Ensure data consistency before running
        _ensure_agent_data_consistency()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("\nThis appears to be a bug in the agent configuration.", file=sys.stderr)
        print("Please report this issue.", file=sys.stderr)
        sys.exit(1)

    try:
        parser = argparse.ArgumentParser(
            description="Multi-agent code review orchestration",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s --suggest              # Suggest agents based on context
  %(prog)s --list                 # List all available agents
  %(prog)s --presets              # List available presets
            """
        )

        parser.add_argument(
            "--suggest",
            action="store_true",
            help="Suggest agents based on current repository context"
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="List all available agents"
        )
        parser.add_argument(
            "--presets",
            action="store_true",
            help="List available presets"
        )
        parser.add_argument(
            "--context",
            action="store_true",
            help="Show detected context information"
        )
        parser.add_argument(
            "--context-json",
            action="store_true",
            help="Output ProjectContext as JSON for 3-Layer Defense filtering"
        )

        args = parser.parse_args()

        if args.suggest:
            try:
                context = detect_context()
            except RuntimeError as e:
                print(f"Error detecting repository context: {e}", file=sys.stderr)
                print("\nCannot suggest agents without context information.", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Unexpected error detecting context: {e}", file=sys.stderr)
                logger.error(f"Context detection failed: {e}", exc_info=True)
                sys.exit(1)

            print("🔍 Detecting repository context...\n")

            if args.context:
                print("Detected Context:")
                print(f"  Has PR: {context['has_pr']}")
                print(f"  Has tests: {context['has_tests']}")
                print(f"  Has types: {context['has_types']}")
                print(f"  Has error handling: {context['has_error_handling']}")
                print(f"  Change size: {context['change_size']} lines")
                print(f"  Staged files: {len(context['staged_files'])}")
                print(f"  Working files: {len(context['working_files'])}")
                print()

            agents = suggest_agents(context)
            print("✅ Suggested agents based on context:\n")
            for agent_name in agents:
                agent = AGENT_MAP.get(agent_name)
                if agent:
                    print(f"  • {agent.name}")
                    print(f"    {agent.description}")
                else:
                    # CRITICAL: Log and report missing agents
                    print(f"  ⚠️  ERROR: Agent '{agent_name}' not found in AGENT_MAP")
                    logger.error(f"Agent '{agent_name}' not found. Valid: {list(AGENT_MAP.keys())}")
            print()

        elif args.list:
            print("Available Agents:\n")
            print(format_agent_list(PRIMARY_AGENTS, "Primary (Recommended)"))
            print(format_agent_list(SPECIALIZED_AGENTS, "Specialized (pr-review-toolkit)"))
            print(format_agent_list(FRAMEWORK_AGENTS, "Framework-Specific"))
            print()

        elif args.presets:
            print("Available Presets:\n")
            for name, agents in AGENT_PRESETS.items():
                print(f"  {name}: {', '.join(agents)}")
            print()

        elif args.context:
            print("Repository Context:\n")
            try:
                context = detect_context()
            except RuntimeError as e:
                print(f"Error detecting repository context: {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"Unexpected error detecting context: {e}", file=sys.stderr)
                logger.error(f"Context detection failed: {e}", exc_info=True)
                sys.exit(1)

            print(f"  Has PR: {context['has_pr']}")
            print(f"  Has tests: {context['has_tests']}")
            print(f"  Has types: {context['has_types']}")
            print(f"  Has error handling: {context['has_error_handling']}")
            print(f"  Change size: {context['change_size']} lines")
            print(f"  Staged files: {len(context['staged_files'])}")
            print(f"  Working files: {len(context['working_files'])}")

            if context["staged_files"]:
                print(f"\n  Staged files:")
                for f in context["staged_files"][:10]:
                    print(f"    - {f}")
                if len(context["staged_files"]) > 10:
                    print(f"    ... and {len(context['staged_files']) - 10} more")

            if context["working_files"]:
                print(f"\n  Working files:")
                for f in context["working_files"][:10]:
                    print(f"    - {f}")
                if len(context["working_files"]) > 10:
                    print(f"    ... and {len(context['working_files']) - 10} more")

            print()

        elif args.context_json:
            # Output ProjectContext as JSON for 3-Layer Defense filtering
            try:
                project_ctx = build_project_context()
                print(json.dumps(project_ctx.to_dict(), indent=2))
            except Exception as e:
                print(f"Error building project context: {e}", file=sys.stderr)
                logger.error(f"Failed to build project context: {e}", exc_info=True)
                sys.exit(1)

        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)  # Standard exit code for SIGINT
    except MemoryError:
        print("Out of memory. The repository may be too large.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        logger.error(f"Unhandled exception in main(): {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
