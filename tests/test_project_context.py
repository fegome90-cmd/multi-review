#!/usr/bin/env python3
"""
Unit tests for project_context.py.

Tests for:
- EvidenceLevel enum values
- ConfigValue immutability and behavior
- PythonConfig/ShellConfig/TestConfig/GitMetadata defaults
- ProjectContext creation and context_hash generation
"""

import pytest
from pathlib import Path

# Add scripts to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from project_context import (
    EvidenceLevel,
    ConfigValue,
    PythonConfig,
    ShellConfig,
    TestConfig,
    GitMetadata,
    ProjectContext,
)


class TestEvidenceLevel:
    """Tests for EvidenceLevel enum."""

    def test_evidence_level_values(self):
        """Test that EvidenceLevel has correct values."""
        assert EvidenceLevel.FACT.value == "fact"
        assert EvidenceLevel.HEURISTIC.value == "heuristic"
        assert EvidenceLevel.ASSUMPTION.value == "assumption"

    def test_evidence_level_count(self):
        """Test that there are exactly 3 evidence levels."""
        assert len(EvidenceLevel) == 3


class TestConfigValue:
    """Tests for ConfigValue dataclass."""

    def test_config_value_creation(self):
        """Test creating a ConfigValue."""
        cv = ConfigValue(True, EvidenceLevel.FACT, "test source")
        assert cv.value is True
        assert cv.evidence == EvidenceLevel.FACT
        assert cv.source == "test source"

    def test_config_value_immutability(self):
        """Test that ConfigValue is immutable (frozen)."""
        cv = ConfigValue(42, EvidenceLevel.HEURISTIC, "test")
        with pytest.raises(AttributeError):
            cv.value = 100

    def test_config_value_bool_true(self):
        """Test boolean conversion with truthy value."""
        cv = ConfigValue(True, EvidenceLevel.FACT, "test")
        assert bool(cv) is True

    def test_config_value_bool_false(self):
        """Test boolean conversion with falsy value."""
        cv = ConfigValue(False, EvidenceLevel.FACT, "test")
        assert bool(cv) is False

    def test_config_value_bool_empty_string(self):
        """Test boolean conversion with empty string."""
        cv = ConfigValue("", EvidenceLevel.ASSUMPTION, "test")
        assert bool(cv) is False

    def test_config_value_bool_non_empty_string(self):
        """Test boolean conversion with non-empty string."""
        cv = ConfigValue("value", EvidenceLevel.HEURISTIC, "test")
        assert bool(cv) is True


class TestPythonConfig:
    """Tests for PythonConfig dataclass."""

    def test_python_config_default(self):
        """Test default PythonConfig creation."""
        config = PythonConfig.default()
        assert config.mypy_strict.value is False
        assert config.mypy_strict.evidence == EvidenceLevel.ASSUMPTION
        assert config.ruff_rules == frozenset()
        assert config.type_checking_level.value == "none"
        assert config.uses_result_pattern.value is False

    def test_python_config_custom(self):
        """Test custom PythonConfig creation."""
        config = PythonConfig(
            mypy_strict=ConfigValue(True, EvidenceLevel.FACT, "pyproject.toml"),
            mypy_configured=ConfigValue(True, EvidenceLevel.FACT, "pyproject.toml"),
            ruff_rules=frozenset(["E", "F", "I"]),
            type_checking_level=ConfigValue("strict", EvidenceLevel.FACT, "mypy config"),
            uses_result_pattern=ConfigValue(True, EvidenceLevel.HEURISTIC, "detected"),
        )
        assert config.mypy_strict.value is True
        assert "E" in config.ruff_rules
        assert config.type_checking_level.value == "strict"

    def test_python_config_immutability(self):
        """Test that PythonConfig is immutable."""
        config = PythonConfig.default()
        with pytest.raises(AttributeError):
            config.mypy_strict = ConfigValue(True, EvidenceLevel.FACT, "test")


class TestShellConfig:
    """Tests for ShellConfig dataclass."""

    def test_shell_config_default(self):
        """Test default ShellConfig creation."""
        config = ShellConfig.default()
        assert config.strict_mode_files == frozenset()
        assert config.detection_evidence == frozenset()
        assert config.has_any_shell_scripts.value is False

    def test_shell_config_with_strict_mode(self):
        """Test ShellConfig with detected strict mode files."""
        config = ShellConfig(
            strict_mode_files=frozenset([Path("script.sh")]),
            detection_evidence=frozenset(["script.sh:1:set -euo pipefail"]),
            has_any_shell_scripts=ConfigValue(True, EvidenceLevel.FACT, "found"),
        )
        assert Path("script.sh") in config.strict_mode_files
        assert len(config.detection_evidence) == 1


class TestTestConfig:
    """Tests for TestConfig dataclass."""

    def test_test_config_default(self):
        """Test default TestConfig creation."""
        config = TestConfig.default()
        assert config.has_tests.value is False
        assert config.test_framework.value == "none"
        assert config.coverage_tool.value == "none"

    def test_test_config_with_pytest(self):
        """Test TestConfig with pytest detected."""
        config = TestConfig(
            has_tests=ConfigValue(True, EvidenceLevel.FACT, "test files found"),
            test_framework=ConfigValue("pytest", EvidenceLevel.HEURISTIC, "conftest.py"),
            coverage_tool=ConfigValue("pytest-cov", EvidenceLevel.HEURISTIC, "pyproject.toml"),
            min_coverage_threshold=ConfigValue(80, EvidenceLevel.FACT, "pyproject.toml"),
        )
        assert config.has_tests.value is True
        assert config.test_framework.value == "pytest"


class TestGitMetadata:
    """Tests for GitMetadata dataclass."""

    def test_git_metadata_default(self):
        """Test default GitMetadata creation."""
        meta = GitMetadata.default()
        assert meta.has_git.value is False
        assert meta.main_branch.value == "main"
        assert meta.pre_existing_issue_authors == frozenset()

    def test_git_metadata_with_repo(self):
        """Test GitMetadata with git repository detected."""
        meta = GitMetadata(
            has_git=ConfigValue(True, EvidenceLevel.FACT, ".git found"),
            main_branch=ConfigValue("main", EvidenceLevel.FACT, "git remote show"),
            pre_existing_issue_authors=frozenset(["Alice", "Bob"]),
            changed_files=frozenset(["src/main.py", "tests/test_main.py"]),
        )
        assert meta.has_git.value is True
        assert "Alice" in meta.pre_existing_issue_authors
        assert len(meta.changed_files) == 2


class TestProjectContext:
    """Tests for ProjectContext dataclass."""

    def test_project_context_default(self):
        """Test default ProjectContext creation."""
        context = ProjectContext.default()
        assert isinstance(context.python_config, PythonConfig)
        assert isinstance(context.shell_config, ShellConfig)
        assert isinstance(context.test_config, TestConfig)
        assert isinstance(context.git_metadata, GitMetadata)

    def test_project_context_schema_version(self):
        """Test that schema version is defined."""
        context = ProjectContext.default()
        assert context.SCHEMA_VERSION == "1.0.0"
        assert context.FILTER_RULES_VERSION == "1.0.0"

    def test_project_context_hash_deterministic(self):
        """Test that context hash is deterministic."""
        context = ProjectContext.default()
        hash1 = context.to_context_hash()
        hash2 = context.to_context_hash()
        assert hash1 == hash2
        assert len(hash1) == 16  # 16 hex characters

    def test_project_context_hash_changes_with_config(self):
        """Test that context hash changes with configuration."""
        context1 = ProjectContext.default()

        # Create context with different config
        python_config = PythonConfig(
            mypy_strict=ConfigValue(True, EvidenceLevel.FACT, "test"),
            mypy_configured=ConfigValue(True, EvidenceLevel.FACT, "test"),
            ruff_rules=frozenset(["E"]),
            type_checking_level=ConfigValue("strict", EvidenceLevel.FACT, "test"),
            uses_result_pattern=ConfigValue(False, EvidenceLevel.ASSUMPTION, "test"),
        )
        context2 = ProjectContext(
            python_config=python_config,
            shell_config=ShellConfig.default(),
            test_config=TestConfig.default(),
            git_metadata=GitMetadata.default(),
        )

        assert context1.to_context_hash() != context2.to_context_hash()

    def test_project_context_to_dict(self):
        """Test converting ProjectContext to dictionary."""
        context = ProjectContext.default()
        d = context.to_dict()

        assert "schema_version" in d
        assert "filter_rules_version" in d
        assert "context_hash" in d
        assert "python_config" in d
        assert "shell_config" in d
        assert "test_config" in d
        assert "git_metadata" in d

    def test_project_context_hash_includes_strict_mode_files(self):
        """Test that hash includes strict mode files."""
        context1 = ProjectContext.default()

        shell_config = ShellConfig(
            strict_mode_files=frozenset([Path("script.sh")]),
            detection_evidence=frozenset(["evidence"]),
            has_any_shell_scripts=ConfigValue(True, EvidenceLevel.FACT, "found"),
        )
        context2 = ProjectContext(
            python_config=PythonConfig.default(),
            shell_config=shell_config,
            test_config=TestConfig.default(),
            git_metadata=GitMetadata.default(),
        )

        assert context1.to_context_hash() != context2.to_context_hash()

    def test_project_context_hash_same_for_same_config(self):
        """Test that identical configs produce same hash."""
        context1 = ProjectContext.default()
        context2 = ProjectContext.default()

        assert context1.to_context_hash() == context2.to_context_hash()

    def test_project_context_immutability(self):
        """Test that ProjectContext is immutable."""
        context = ProjectContext.default()
        with pytest.raises(AttributeError):
            context.SCHEMA_VERSION = "2.0.0"
