"""Tests for context_detector.py module."""

import pytest

from context_detector import (
    Agent,
    AGENT_PRESETS,
    PRIMARY_AGENTS,
    SPECIALIZED_AGENTS,
    FRAMEWORK_AGENTS,
    ALL_AGENTS,
    AGENT_MAP,
    _validate_agent_name,
    detect_context,
    suggest_agents,
)


class TestAgentValidation:
    """Tests for agent name validation."""

    def test_validate_valid_agent_name(self):
        """Valid agent names should pass validation."""
        # Should not raise
        _validate_agent_name("feature-dev:code-reviewer")
        _validate_agent_name("pr-review-toolkit:test-analyzer")
        _validate_agent_name("superpowers:review-checklist")

    def test_validate_empty_agent_name(self):
        """Empty agent name should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_agent_name("")

    def test_validate_whitespace_in_name(self):
        """Agent names with whitespace should raise ValueError."""
        with pytest.raises(ValueError, match="whitespace"):
            _validate_agent_name("feature dev:code-reviewer")

        with pytest.raises(ValueError, match="whitespace"):
            _validate_agent_name("feature-dev:code reviewer")

    def test_validate_invalid_format(self):
        """Agent names without colon separator should raise ValueError."""
        with pytest.raises(ValueError, match="format"):
            _validate_agent_name("feature-dev-code-reviewer")

        with pytest.raises(ValueError, match="format"):
            _validate_agent_name("feature-dev:code:reviewer")

    def test_validate_empty_namespace(self):
        """Empty namespace should raise ValueError."""
        with pytest.raises(ValueError, match="namespace.*non-empty"):
            _validate_agent_name(":code-reviewer")

    def test_validate_empty_agent_name_part(self):
        """Empty agent name part should raise ValueError."""
        with pytest.raises(ValueError, match="agent name.*non-empty"):
            _validate_agent_name("feature-dev:")


class TestAgentDataclass:
    """Tests for Agent dataclass with validation."""

    def test_create_valid_agent(self):
        """Creating a valid agent should work."""
        agent = Agent("feature-dev:code-reviewer", "General review", "feature-dev")
        assert agent.name == "feature-dev:code-reviewer"
        assert agent.description == "General review"
        assert agent.source == "feature-dev"

    def test_agent_frozen_immutable(self):
        """Agent dataclass should be frozen (immutable)."""
        agent = Agent("feature-dev:code-reviewer", "General review", "feature-dev")
        with pytest.raises(Exception):  # FrozenInstanceError
            agent.name = "other"

    def test_agent_post_init_validation_invalid_name(self):
        """Agent with invalid name should raise ValueError on creation."""
        with pytest.raises(ValueError, match="format"):
            Agent("invalid-name", "Description", "feature-dev")

    def test_agent_post_init_validation_invalid_source(self):
        """Agent with invalid source should raise ValueError on creation."""
        with pytest.raises(ValueError, match="Invalid agent source"):
            Agent("feature-dev:code-reviewer", "Description", "invalid-source")


class TestAgentPresets:
    """Tests for agent preset configurations."""

    def test_quick_preset_has_two_agents(self):
        """Quick preset should have exactly 2 agents."""
        quick = AGENT_PRESETS["quick"]
        assert len(quick) == 2
        assert "feature-dev:code-reviewer" in quick
        assert "pr-review-toolkit:code-simplifier" in quick

    def test_thorough_preset_has_four_agents(self):
        """Thorough preset should have exactly 4 agents."""
        thorough = AGENT_PRESETS["thorough"]
        assert len(thorough) == 4

    def test_comprehensive_preset_has_all_specialized(self):
        """Comprehensive preset should include all specialized agents."""
        comprehensive = AGENT_PRESETS["comprehensive"]
        assert len(comprehensive) == 7

    def test_framework_preset(self):
        """Framework preset should have superpowers agent."""
        framework = AGENT_PRESETS["framework"]
        assert len(framework) == 1
        assert "superpowers:code-review-checklist" in framework

    def test_all_preset_agents_exist_in_map(self):
        """All agents in presets should exist in AGENT_MAP."""
        for preset_name, agents in AGENT_PRESETS.items():
            for agent_name in agents:
                assert agent_name in AGENT_MAP, f"{agent_name} in {preset_name} not in AGENT_MAP"


class TestAgentLists:
    """Tests for agent list definitions."""

    def test_primary_agents_not_empty(self):
        """PRIMARY_AGENTS should not be empty."""
        assert len(PRIMARY_AGENTS) > 0

    def test_specialized_agents_not_empty(self):
        """SPECIALIZED_AGENTS should not be empty."""
        assert len(SPECIALIZED_AGENTS) > 0

    def test_all_agents_is_union(self):
        """ALL_AGENTS should be union of other lists."""
        expected = PRIMARY_AGENTS + SPECIALIZED_AGENTS + FRAMEWORK_AGENTS
        assert ALL_AGENTS == expected

    def test_agent_map_contains_all_agents(self):
        """AGENT_MAP should contain all agents from ALL_AGENTS."""
        assert len(AGENT_MAP) == len(ALL_AGENTS)
        for agent in ALL_AGENTS:
            assert agent.name in AGENT_MAP


class TestSuggestAgents:
    """Tests for suggest_agents function."""

    def test_suggest_for_small_change(self, sample_context):
        """Small changes should suggest quick preset."""
        sample_context["change_size"] = 30
        sample_context["has_tests"] = False
        agents = suggest_agents(sample_context)
        assert "feature-dev:code-reviewer" in agents

    def test_suggest_for_large_change(self, sample_context):
        """Large changes should suggest comprehensive preset."""
        sample_context["change_size"] = 600
        agents = suggest_agents(sample_context)
        # Should include more agents for large changes
        assert len(agents) >= 4

    def test_suggest_with_tests(self, sample_context):
        """Changes with tests should include test analyzer."""
        sample_context["has_tests"] = True
        agents = suggest_agents(sample_context)
        assert "pr-review-toolkit:pr-test-analyzer" in agents

    def test_suggest_with_types(self, sample_context):
        """Changes with type definitions should include type analyzer."""
        sample_context["has_types"] = True
        agents = suggest_agents(sample_context)
        assert "pr-review-toolkit:type-design-analyzer" in agents


class TestDetectContext:
    """Tests for detect_context function."""

    def test_detect_context_returns_dict(self):
        """detect_context should return a dictionary."""
        context = detect_context()
        assert isinstance(context, dict)

    def test_detect_context_has_required_keys(self):
        """detect_context should have all required keys."""
        context = detect_context()
        required_keys = [
            "has_pr", "has_tests", "has_types",
            "has_error_handling", "has_comments", "change_size",
            "staged_files", "working_files"
        ]
        for key in required_keys:
            assert key in context


@pytest.mark.integration
class TestGitOperations:
    """Integration tests that require git operations."""

    def test_detect_context_in_git_repo(self):
        """Should detect context in a git repository."""
        context = detect_context()
        # This test runs in a git repo (the plugin itself)
        assert isinstance(context["change_size"], int)
        assert isinstance(context["staged_files"], list)
