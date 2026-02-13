#!/usr/bin/env python3
"""
Project context data structures for multi-review false positive elimination.

This module provides the data structures that enable the 3-Layer Defense system:
- Layer 1: Context Injection (facts from project config)
- Layer 2: Mechanical Filtering (typed predicates)
- Layer 3: Evidence-Based Validation (tool outputs)

Key Design Principle: Separate FACTS (parsed from config) from HEURISTICS
(inferred by pattern matching) from ASSUMPTIONS (defaults when no evidence).

Dependencies:
    - Python 3.10+ stdlib only (no external dependencies)
"""

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional


class EvidenceLevel(Enum):
    """Classification of how a config value was determined.

    This enables the system to distinguish between:
    - FACT: Derived from parsing config files (high confidence)
    - HEURISTIC: Inferred by pattern matching (medium confidence)
    - ASSUMPTION: Default value when no evidence exists (low confidence)
    """
    FACT = "fact"
    HEURISTIC = "heuristic"
    ASSUMPTION = "assumption"


@dataclass(frozen=True)
class ConfigValue:
    """A configuration value with evidence level.

    Attributes:
        value: The actual configuration value.
        evidence: How this value was determined (FACT/HEURISTIC/ASSUMPTION).
        source: Human-readable description of where this came from.

    Example:
        >>> ConfigValue(True, EvidenceLevel.FACT, "pyproject.toml [tool.mypy].strict")
        ConfigValue(value=True, evidence=<EvidenceLevel.FACT: 'fact'>, ...)
    """
    value: Any
    evidence: EvidenceLevel
    source: str

    def __bool__(self) -> bool:
        """Allow using ConfigValue in boolean context."""
        return bool(self.value)


@dataclass(frozen=True)
class PythonConfig:
    """Python project configuration extracted from config files.

    All fields use ConfigValue to track evidence level.

    Attributes:
        mypy_strict: Whether mypy strict mode is enabled.
        mypy_configured: Whether any mypy configuration exists.
        ruff_rules: Set of enabled ruff rules (FACT from pyproject.toml).
        type_checking_level: Overall type checking strictness.
        uses_result_pattern: Whether the project uses Result/Either pattern.
        result_pattern_evidence: Evidence for Result pattern detection.
    """
    mypy_strict: ConfigValue
    mypy_configured: ConfigValue
    ruff_rules: FrozenSet[str]
    type_checking_level: ConfigValue  # "strict", "moderate", "relaxed", "none"
    uses_result_pattern: ConfigValue
    result_pattern_evidence: FrozenSet[str] = field(default_factory=frozenset)

    @classmethod
    def default(cls) -> "PythonConfig":
        """Create default PythonConfig with ASSUMPTION evidence levels."""
        return cls(
            mypy_strict=ConfigValue(False, EvidenceLevel.ASSUMPTION, "no mypy config found"),
            mypy_configured=ConfigValue(False, EvidenceLevel.ASSUMPTION, "no mypy config found"),
            ruff_rules=frozenset(),
            type_checking_level=ConfigValue("none", EvidenceLevel.ASSUMPTION, "no type checker configured"),
            uses_result_pattern=ConfigValue(False, EvidenceLevel.ASSUMPTION, "no Result imports detected"),
            result_pattern_evidence=frozenset(),
        )


@dataclass(frozen=True)
class ShellConfig:
    """Shell script configuration for the project.

    Attributes:
        strict_mode_files: Set of shell files with `set -euo pipefail` (FACT).
        detection_evidence: Map of file -> exact line that triggered detection.
        has_any_shell_scripts: Whether project contains shell scripts.
    """
    strict_mode_files: FrozenSet[Path]
    detection_evidence: FrozenSet[str]  # "filepath:line" format
    has_any_shell_scripts: ConfigValue

    @classmethod
    def default(cls) -> "ShellConfig":
        """Create default ShellConfig with ASSUMPTION evidence levels."""
        return cls(
            strict_mode_files=frozenset(),
            detection_evidence=frozenset(),
            has_any_shell_scripts=ConfigValue(False, EvidenceLevel.ASSUMPTION, "no shell files found"),
        )


@dataclass(frozen=True)
class TestConfig:
    """Test configuration for the project.

    Attributes:
        has_tests: Whether test files exist.
        test_framework: Detected test framework (pytest, unittest, jest, etc.).
        coverage_tool: Detected coverage tool (coverage.py, pytest-cov, etc.).
        min_coverage_threshold: Minimum coverage threshold if configured.
    """
    has_tests: ConfigValue
    test_framework: ConfigValue  # "pytest", "unittest", "jest", "vitest", "none"
    coverage_tool: ConfigValue
    min_coverage_threshold: ConfigValue  # int or None

    @classmethod
    def default(cls) -> "TestConfig":
        """Create default TestConfig with ASSUMPTION evidence levels."""
        return cls(
            has_tests=ConfigValue(False, EvidenceLevel.ASSUMPTION, "no test files found"),
            test_framework=ConfigValue("none", EvidenceLevel.ASSUMPTION, "no test framework detected"),
            coverage_tool=ConfigValue("none", EvidenceLevel.ASSUMPTION, "no coverage tool detected"),
            min_coverage_threshold=ConfigValue(None, EvidenceLevel.ASSUMPTION, "no coverage threshold configured"),
        )


@dataclass(frozen=True)
class GitMetadata:
    """Git metadata for the project.

    Attributes:
        has_git: Whether this is a git repository.
        main_branch: Name of the main branch.
        pre_existing_issue_authors: Authors of lines that might be pre-existing issues.
        changed_files: List of files with changes (staged or working).
    """
    has_git: ConfigValue
    main_branch: ConfigValue
    pre_existing_issue_authors: FrozenSet[str]
    changed_files: FrozenSet[str]

    @classmethod
    def default(cls) -> "GitMetadata":
        """Create default GitMetadata with ASSUMPTION evidence levels."""
        return cls(
            has_git=ConfigValue(False, EvidenceLevel.ASSUMPTION, "not a git repository"),
            main_branch=ConfigValue("main", EvidenceLevel.ASSUMPTION, "default assumption"),
            pre_existing_issue_authors=frozenset(),
            changed_files=frozenset(),
        )


@dataclass(frozen=True)
class ProjectContext:
    """Complete project context for false positive elimination.

    This is the main data structure passed through the 3-Layer Defense system.
    It captures all relevant project configuration to enable context-aware filtering.

    Attributes:
        python_config: Python-specific configuration.
        shell_config: Shell script configuration.
        test_config: Test configuration.
        git_metadata: Git repository metadata.
        SCHEMA_VERSION: Version of this data structure (for cache invalidation).

    Example:
        >>> context = ProjectContext(
        ...     python_config=PythonConfig.default(),
        ...     shell_config=ShellConfig.default(),
        ...     test_config=TestConfig.default(),
        ...     git_metadata=GitMetadata.default(),
        ... )
        >>> context.to_context_hash()
        'a1b2c3d4e5f6...'
    """
    python_config: PythonConfig
    shell_config: ShellConfig
    test_config: TestConfig
    git_metadata: GitMetadata

    # Schema version - bump when structure changes (breaks cache)
    SCHEMA_VERSION: str = "1.0.0"
    # Filter rules version - bump when Layer 2 rules change
    FILTER_RULES_VERSION: str = "1.0.0"

    def to_context_hash(self) -> str:
        """Generate hash for cache invalidation.

        The hash includes:
        - Schema version (structure changes)
        - Filter rules version (Layer 2 changes)
        - Python config (mypy, ruff, type checking)
        - Shell config (strict mode files)

        Returns:
            16-character hex string (truncated SHA256).

        Note:
            Changes to test_config and git_metadata do NOT invalidate cache
            as they don't affect calibration.
        """
        content = f"""
schema:{self.SCHEMA_VERSION}
filter_rules:{self.FILTER_RULES_VERSION}
mypy_strict:{self.python_config.mypy_strict.value}
mypy_configured:{self.python_config.mypy_configured.value}
type_checking:{self.python_config.type_checking_level.value}
ruff_rules:{sorted(self.python_config.ruff_rules)}
result_pattern:{self.python_config.uses_result_pattern.value}
strict_mode_files:{sorted(str(p) for p in self.shell_config.strict_mode_files)}
"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @classmethod
    def default(cls) -> "ProjectContext":
        """Create default ProjectContext with all ASSUMPTION values."""
        return cls(
            python_config=PythonConfig.default(),
            shell_config=ShellConfig.default(),
            test_config=TestConfig.default(),
            git_metadata=GitMetadata.default(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation suitable for JSON serialization.
        """
        return {
            "schema_version": self.SCHEMA_VERSION,
            "filter_rules_version": self.FILTER_RULES_VERSION,
            "context_hash": self.to_context_hash(),
            "python_config": {
                "mypy_strict": self.python_config.mypy_strict.value,
                "mypy_strict_evidence": self.python_config.mypy_strict.evidence.value,
                "mypy_configured": self.python_config.mypy_configured.value,
                "type_checking_level": self.python_config.type_checking_level.value,
                "ruff_rules": sorted(self.python_config.ruff_rules),
                "uses_result_pattern": self.python_config.uses_result_pattern.value,
                "result_pattern_evidence": sorted(self.python_config.result_pattern_evidence),
            },
            "shell_config": {
                "strict_mode_files": sorted(str(p) for p in self.shell_config.strict_mode_files),
                "has_any_shell_scripts": self.shell_config.has_any_shell_scripts.value,
            },
            "test_config": {
                "has_tests": self.test_config.has_tests.value,
                "test_framework": self.test_config.test_framework.value,
                "coverage_tool": self.test_config.coverage_tool.value,
            },
            "git_metadata": {
                "has_git": self.git_metadata.has_git.value,
                "main_branch": self.git_metadata.main_branch.value,
                "changed_files_count": len(self.git_metadata.changed_files),
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectContext":
        """Create ProjectContext from dictionary.

        Args:
            data: Dictionary representation (from to_dict() or JSON).

        Returns:
            ProjectContext instance.

        Note:
            This is a simplified reconstruction that uses default values
            for fields not stored in the dictionary representation.
        """
        # Extract python config
        py_data = data.get("python_config", {})
        python_config = PythonConfig(
            mypy_strict=ConfigValue(
                py_data.get("mypy_strict", False),
                EvidenceLevel.FACT if py_data.get("mypy_strict") else EvidenceLevel.ASSUMPTION,
                "from context",
            ),
            mypy_configured=ConfigValue(
                py_data.get("mypy_configured", False),
                EvidenceLevel.FACT if py_data.get("mypy_configured") else EvidenceLevel.ASSUMPTION,
                "from context",
            ),
            ruff_rules=frozenset(py_data.get("ruff_rules", [])),
            type_checking_level=ConfigValue(
                py_data.get("type_checking_level", "none"),
                EvidenceLevel(py_data.get("mypy_strict_evidence", "assumption")),
                "from context",
            ),
            uses_result_pattern=ConfigValue(
                py_data.get("uses_result_pattern", False),
                EvidenceLevel.HEURISTIC if py_data.get("uses_result_pattern") else EvidenceLevel.ASSUMPTION,
                "from context",
            ),
            result_pattern_evidence=frozenset(py_data.get("result_pattern_evidence", [])),
        )

        # Extract shell config
        sh_data = data.get("shell_config", {})
        shell_config = ShellConfig(
            strict_mode_files=frozenset(Path(p) for p in sh_data.get("strict_mode_files", [])),
            detection_evidence=frozenset(),  # Not stored in to_dict
            has_any_shell_scripts=ConfigValue(
                bool(sh_data.get("strict_mode_files")),
                EvidenceLevel.FACT,
                "from context",
            ),
        )

        # Extract test config
        te_data = data.get("test_config", {})
        test_config = TestConfig(
            has_tests=ConfigValue(
                te_data.get("has_tests", False),
                EvidenceLevel.FACT if te_data.get("has_tests") else EvidenceLevel.ASSUMPTION,
                "from context",
            ),
            test_framework=ConfigValue(
                te_data.get("test_framework", "none"),
                EvidenceLevel.HEURISTIC if te_data.get("has_tests") else EvidenceLevel.ASSUMPTION,
                "from context",
            ),
            coverage_tool=ConfigValue(
                te_data.get("coverage_tool", "none"),
                EvidenceLevel.ASSUMPTION,
                "from context",
            ),
            min_coverage_threshold=ConfigValue(
                te_data.get("min_coverage_threshold"),
                EvidenceLevel.ASSUMPTION,
                "from context",
            ),
        )

        # Extract git metadata
        git_data = data.get("git_metadata", {})
        git_metadata = GitMetadata(
            has_git=ConfigValue(
                git_data.get("has_git", False),
                EvidenceLevel.FACT,
                "from context",
            ),
            main_branch=ConfigValue(
                git_data.get("main_branch", "main"),
                EvidenceLevel.FACT,
                "from context",
            ),
            pre_existing_issue_authors=frozenset(),  # Not stored in to_dict
            changed_files=frozenset(),  # Not stored in to_dict
        )

        return cls(
            python_config=python_config,
            shell_config=shell_config,
            test_config=test_config,
            git_metadata=git_metadata,
        )
