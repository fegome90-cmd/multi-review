#!/usr/bin/env python3
"""
Tests for dspy_client module.

Run with: pytest tests/test_dspy_client.py -v
"""

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from dspy_client import (
    CachedPrompt,
    DSPyClient,
    get_default_prompt,
    get_calibrated_prompt,
    DEFAULT_TTL_DAYS,
)


class TestCachedPrompt:
    """Tests for CachedPrompt dataclass."""

    def test_create_cached_prompt(self):
        """Test creating a cached prompt."""
        cached = CachedPrompt(
            context_hash="abc123",
            agent_name="test-agent",
            calibrated_prompt="Test prompt",
            guardrails=["Rule 1", "Rule 2"],
            created_at="2026-02-13T12:00:00",
        )

        assert cached.context_hash == "abc123"
        assert cached.agent_name == "test-agent"
        assert cached.calibrated_prompt == "Test prompt"
        assert len(cached.guardrails) == 2

    def test_integrity_hash_auto_calculated(self):
        """Test integrity hash is auto-calculated."""
        cached = CachedPrompt(
            context_hash="test",
            agent_name="agent",
            calibrated_prompt="prompt",
            guardrails=["g1"],
            created_at="2026-02-13T12:00:00",
        )

        # Hash should be calculated
        assert cached.integrity_hash is not None
        assert len(cached.integrity_hash) == 16

    def test_verify_integrity_valid(self):
        """Test integrity verification with valid hash."""
        cached = CachedPrompt(
            context_hash="test",
            agent_name="agent",
            calibrated_prompt="prompt",
            guardrails=["g1"],
            created_at="2026-02-13T12:00:00",
        )

        assert cached.verify_integrity() is True

    def test_verify_integrity_invalid(self):
        """Test integrity verification with tampered hash."""
        cached = CachedPrompt(
            context_hash="test",
            agent_name="agent",
            calibrated_prompt="prompt",
            guardrails=["g1"],
            created_at="2026-02-13T12:00:00",
            integrity_hash="tampered12345678",  # Wrong hash
        )

        assert cached.verify_integrity() is False

    def test_is_expired_not_expired(self):
        """Test expiry check for fresh prompt."""
        cached = CachedPrompt(
            context_hash="test",
            agent_name="agent",
            calibrated_prompt="prompt",
            guardrails=[],
            created_at=datetime.now().isoformat(),
            ttl_days=7,
        )

        assert cached.is_expired() is False

    def test_is_expired_expired(self):
        """Test expiry check for old prompt."""
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        cached = CachedPrompt(
            context_hash="test",
            agent_name="agent",
            calibrated_prompt="prompt",
            guardrails=[],
            created_at=old_date,
            ttl_days=7,
        )

        assert cached.is_expired() is True

    def test_is_expired_invalid_date(self):
        """Test expiry check with invalid date."""
        cached = CachedPrompt(
            context_hash="test",
            agent_name="agent",
            calibrated_prompt="prompt",
            guardrails=[],
            created_at="invalid-date",
            ttl_days=7,
        )

        # Invalid date should be treated as expired
        assert cached.is_expired() is True

    def test_to_dict(self):
        """Test serialization to dict."""
        cached = CachedPrompt(
            context_hash="test",
            agent_name="agent",
            calibrated_prompt="prompt",
            guardrails=["g1"],
            created_at="2026-02-13T12:00:00",
        )

        data = cached.to_dict()
        assert data["context_hash"] == "test"
        assert data["agent_name"] == "agent"
        assert "integrity_hash" in data

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "context_hash": "test",
            "agent_name": "agent",
            "calibrated_prompt": "prompt",
            "guardrails": ["g1"],
            "created_at": "2026-02-13T12:00:00",
            "ttl_days": 7,
            "integrity_hash": "abc123def456",
        }

        cached = CachedPrompt.from_dict(data)
        assert cached.context_hash == "test"
        assert cached.ttl_days == 7


class TestGetDefaultPrompt:
    """Tests for get_default_prompt function."""

    def test_existing_agent(self):
        """Test getting prompt for existing agent."""
        prompt = get_default_prompt("feature-dev:code-reviewer")

        assert "calibrated_prompt" in prompt
        assert "guardrails" in prompt
        assert "Security vulnerabilities" in prompt["calibrated_prompt"]

    def test_unknown_agent_returns_fallback(self):
        """Test unknown agent returns fallback prompt."""
        prompt = get_default_prompt("unknown:agent")

        assert "calibrated_prompt" in prompt
        assert "guardrails" in prompt
        # Should have generic prompt
        assert "confidence" in prompt["calibrated_prompt"].lower()


class TestDSPyClient:
    """Tests for DSPyClient class."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temp cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_initialization(self, temp_cache_dir):
        """Test client initialization."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        assert client.cache_dir == temp_cache_dir
        assert client.ttl_days == DEFAULT_TTL_DAYS

    def test_get_cache_path(self, temp_cache_dir):
        """Test cache path generation."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        path = client._get_cache_path("abc123")
        assert path == temp_cache_dir / "abc123.json"

    def test_build_review_prompt_default(self, temp_cache_dir):
        """Test build_review_prompt returns default when no cache."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Create mock context
        mock_context = MagicMock()
        mock_context.to_context_hash.return_value = "test-hash"

        prompt = client.build_review_prompt("feature-dev:code-reviewer", mock_context)

        assert "Security vulnerabilities" in prompt
        assert len(prompt) > 100  # Should have substantial content

    def test_get_guardrails_default(self, temp_cache_dir):
        """Test get_guardrails returns default when no cache."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        mock_context = MagicMock()
        mock_context.to_context_hash.return_value = "test-hash"

        guardrails = client.get_guardrails("feature-dev:code-reviewer", mock_context)

        assert len(guardrails) >= 1
        assert any("linters" in g for g in guardrails)

    def test_save_and_load_cached_prompt(self, temp_cache_dir):
        """Test saving and loading cached prompt."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        cached = CachedPrompt(
            context_hash="test-hash",
            agent_name="test-agent",
            calibrated_prompt="Test prompt content",
            guardrails=["Rule 1"],
            created_at=datetime.now().isoformat(),
        )

        # Save
        success = client._save_cached_prompt(cached)
        assert success is True

        # Load
        loaded = client._load_cached_prompt("test-hash")
        assert loaded is not None
        assert loaded.calibrated_prompt == "Test prompt content"
        assert loaded.agent_name == "test-agent"

    def test_load_nonexistent_cache(self, temp_cache_dir):
        """Test loading nonexistent cache returns None."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        loaded = client._load_cached_prompt("nonexistent")
        assert loaded is None

    def test_get_cache_stats(self, temp_cache_dir):
        """Test cache statistics."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Save a cached prompt
        cached = CachedPrompt(
            context_hash="stat-test",
            agent_name="agent",
            calibrated_prompt="prompt",
            guardrails=[],
            created_at=datetime.now().isoformat(),
        )
        client._save_cached_prompt(cached)

        stats = client.get_cache_stats()

        assert stats["total_files"] == 1
        assert stats["valid"] == 1
        assert stats["expired"] == 0
        assert stats["corrupted"] == 0

    def test_clear_cache(self, temp_cache_dir):
        """Test clearing cache."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Save a cached prompt
        cached = CachedPrompt(
            context_hash="clear-test",
            agent_name="agent",
            calibrated_prompt="prompt",
            guardrails=[],
            created_at=datetime.now().isoformat(),
        )
        client._save_cached_prompt(cached)

        # Clear
        count = client.clear_cache()
        assert count == 1

        # Verify gone
        stats = client.get_cache_stats()
        assert stats["total_files"] == 0

    def test_precompile_prompts(self, temp_cache_dir):
        """Test precompiling prompts."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        mock_context = MagicMock()
        mock_context.to_context_hash.return_value = "precompile-hash"

        results = client.precompile_prompts(
            ["feature-dev:code-reviewer"],
            [mock_context],
        )

        assert len(results) == 1
        # Should have created a cache entry
        assert any("True" in str(v) or v is True for v in results.values())


class TestGetCalibratedPrompt:
    """Tests for get_calibrated_prompt convenience function."""

    def test_returns_prompt(self):
        """Test that function returns a prompt string."""
        mock_context = MagicMock()
        mock_context.to_context_hash.return_value = "convenience-hash"

        prompt = get_calibrated_prompt("feature-dev:code-reviewer", mock_context)

        assert isinstance(prompt, str)
        assert len(prompt) > 50


class TestDSPyClientCacheErrors:
    """Tests for cache error handling paths."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temp cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_load_corrupted_cache_file(self, temp_cache_dir):
        """Test loading corrupted JSON cache returns None."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Create corrupted cache file
        cache_file = temp_cache_dir / "corrupted.json"
        cache_file.write_text("{ invalid json }", encoding="utf-8")

        # Should return None without crashing
        loaded = client._load_cached_prompt("corrupted")
        assert loaded is None

    def test_load_cache_with_integrity_failure(self, temp_cache_dir):
        """Test loading cache with tampered integrity hash."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Create cache file with wrong integrity hash
        cache_file = temp_cache_dir / "tampered.json"
        data = {
            "context_hash": "tampered",
            "agent_name": "test",
            "calibrated_prompt": "prompt",
            "guardrails": ["g1"],
            "created_at": datetime.now().isoformat(),
            "ttl_days": 7,
            "integrity_hash": "wrong_hash_123",  # Wrong hash
        }
        cache_file.write_text(json.dumps(data), encoding="utf-8")

        # Should return None when integrity fails
        loaded = client._load_cached_prompt("tampered")
        assert loaded is None

    def test_load_cache_with_invalid_date(self, temp_cache_dir):
        """Test loading cache with invalid date format."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Create cache file with invalid date
        cache_file = temp_cache_dir / "bad-date.json"
        data = {
            "context_hash": "bad-date",
            "agent_name": "test",
            "calibrated_prompt": "prompt",
            "guardrails": [],
            "created_at": "not-a-date",
            "ttl_days": 7,
            "integrity_hash": hashlib.sha256(b"prompt").hexdigest()[:16],
        }
        cache_file.write_text(json.dumps(data), encoding="utf-8")

        # Should load but be expired
        loaded = client._load_cached_prompt("bad-date")
        assert loaded is not None
        assert loaded.is_expired() is True

    def test_load_cache_with_missing_fields(self, temp_cache_dir):
        """Test loading cache with missing required fields."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Create cache file with missing fields
        cache_file = temp_cache_dir / "incomplete.json"
        data = {
            "context_hash": "incomplete",
            # Missing agent_name
            "calibrated_prompt": "prompt",
            "guardrails": [],
            "created_at": datetime.now().isoformat(),
        }
        cache_file.write_text(json.dumps(data), encoding="utf-8")

        # Should return None due to TypeError from from_dict
        loaded = client._load_cached_prompt("incomplete")
        assert loaded is None

    def test_save_cache_creates_directory(self, temp_cache_dir):
        """Test saving cache when directory doesn't exist."""
        # Create client with non-existent subdirectory
        subdir = temp_cache_dir / "subdir" / "nested"
        client = DSPyClient(cache_dir=subdir)

        cached = CachedPrompt(
            context_hash="test-hash",
            agent_name="test-agent",
            calibrated_prompt="Test prompt content",
            guardrails=["Rule 1"],
            created_at=datetime.now().isoformat(),
        )

        # Should create directory and save successfully
        success = client._save_cached_prompt(cached)
        assert success is True
        assert subdir.exists()
        assert (subdir / "test-hash.json").exists()

    def test_build_review_prompt_uses_cache(self, temp_cache_dir):
        """Test build_review_prompt returns cached result when available."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Create mock context first
        mock_context = MagicMock()
        mock_context.to_context_hash.return_value = "context-hash-value"

        # Calculate the actual hash client will use
        expected_hash = client._hash_context("test-agent", mock_context)

        # Create valid cache entry with correct hash
        cached = CachedPrompt(
            context_hash=expected_hash,
            agent_name="test-agent",
            calibrated_prompt="CACHED PROMPT CONTENT",
            guardrails=["Rule 1"],
            created_at=datetime.now().isoformat(),
            ttl_days=7,
        )
        client._save_cached_prompt(cached)

        prompt = client.build_review_prompt("test-agent", mock_context)

        # Should return cached content
        assert "CACHED PROMPT CONTENT" in prompt

    def test_get_guardrails_uses_cache(self, temp_cache_dir):
        """Test get_guardrails returns cached result when available."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Create mock context first
        mock_context = MagicMock()
        mock_context.to_context_hash.return_value = "context-hash-value"

        # Calculate the actual hash client will use
        expected_hash = client._hash_context("test-agent", mock_context)

        # Create valid cache entry with correct hash
        cached = CachedPrompt(
            context_hash=expected_hash,
            agent_name="test-agent",
            calibrated_prompt="prompt",
            guardrails=["CACHED RULE 1", "CACHED RULE 2"],
            created_at=datetime.now().isoformat(),
            ttl_days=7,
        )
        client._save_cached_prompt(cached)

        guardrails = client.get_guardrails("test-agent", mock_context)

        # Should return cached guardrails
        assert len(guardrails) == 2
        assert "CACHED RULE 1" in guardrails
        assert "CACHED RULE 2" in guardrails

    def test_cache_stats_with_mixed_files(self, temp_cache_dir):
        """Test cache stats with valid, expired, and corrupted files."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # 1. Valid cache
        valid_cached = CachedPrompt(
            context_hash="valid",
            agent_name="test",
            calibrated_prompt="prompt",
            guardrails=[],
            created_at=datetime.now().isoformat(),
            ttl_days=7,
        )
        client._save_cached_prompt(valid_cached)

        # 2. Expired cache
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        expired_cached = CachedPrompt(
            context_hash="expired",
            agent_name="test",
            calibrated_prompt="prompt",
            guardrails=[],
            created_at=old_date,
            ttl_days=7,
        )
        client._save_cached_prompt(expired_cached)

        # 3. Corrupted JSON
        (temp_cache_dir / "corrupted.json").write_text("{bad}", encoding="utf-8")

        # 4. Tampered integrity
        tampered_data = {
            "context_hash": "tampered",
            "agent_name": "test",
            "calibrated_prompt": "prompt",
            "guardrails": [],
            "created_at": datetime.now().isoformat(),
            "ttl_days": 7,
            "integrity_hash": "wrong",
        }
        (temp_cache_dir / "tampered.json").write_text(
            json.dumps(tampered_data), encoding="utf-8"
        )

        stats = client.get_cache_stats()

        assert stats["total_files"] == 4
        assert stats["valid"] == 1
        assert stats["expired"] == 1
        assert stats["corrupted"] == 2

    def test_clear_cache_with_permission_error(self, temp_cache_dir):
        """Test clear cache handles permission errors gracefully."""
        client = DSPyClient(cache_dir=temp_cache_dir)

        # Create a cache file
        cached = CachedPrompt(
            context_hash="test",
            agent_name="test",
            calibrated_prompt="prompt",
            guardrails=[],
            created_at=datetime.now().isoformat(),
        )
        client._save_cached_prompt(cached)

        # Mock the glob to return a file, then make unlink fail
        original_glob = client.cache_dir.glob

        def mock_glob(pattern):
            for path in original_glob(pattern):
                mock_path = MagicMock()
                mock_path.unlink.side_effect = PermissionError("Denied")
                mock_path.name = path.name
                yield mock_path

        with patch.object(client.cache_dir, "glob", mock_glob):
            # Should not crash, just log warning
            count = client.clear_cache()

        # Should return 0 since nothing was actually deleted
        assert count == 0


class TestDSPyClientRefreshAPI:
    """Tests for refresh_from_api method."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temp cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @patch.dict("sys.modules", {"requests": None})
    def test_refresh_from_api_without_requests(self, temp_cache_dir):
        """Test refresh_from_api returns None when requests not available."""
        client = DSPyClient(cache_dir=temp_cache_dir)
        mock_context = MagicMock()
        result = client.refresh_from_api("test-agent", mock_context)
        assert result is None


class TestRuntimeZeroAPICalls:
    """Tests verifying that runtime NEVER makes API calls."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temp cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_runtime_zero_api_calls(self, temp_cache_dir):
        """Runtime must NEVER make API calls - prompt comes from cache or defaults only."""
        client = DSPyClient(cache_dir=temp_cache_dir)
        mock_context = MagicMock()
        mock_context.to_context_hash.return_value = "test_hash_123"

        # Mock the requests module at the class level
        with patch.object(client, "refresh_from_api") as mock_refresh:
            # Build the prompt (runtime operation)
            prompt = client.build_review_prompt("test-agent", mock_context)

            # refresh_from_api should NEVER be called during runtime
            mock_refresh.assert_not_called()

            # Prompt should be non-empty (from default)
            assert len(prompt) > 0

    def test_build_review_prompt_never_calls_api(self, temp_cache_dir):
        """build_review_prompt must never trigger API calls, only cache lookups."""
        client = DSPyClient(cache_dir=temp_cache_dir)
        mock_context = MagicMock()
        mock_context.to_context_hash.return_value = "hash123"

        # Track if any method that could lead to API calls is invoked
        # build_review_prompt should only call _load_cached_prompt
        with patch.object(client, "_load_cached_prompt") as mock_load:
            mock_load.return_value = None  # Cache miss

            prompt = client.build_review_prompt("test-agent", mock_context)

            # Should only call _load_cached_prompt (cache lookup)
            mock_load.assert_called_once()

            # Should return default prompt (not call API)
            assert "Review the code changes" in prompt or "calibrated" in prompt.lower()

    def test_get_guardrails_never_calls_api(self, temp_cache_dir):
        """get_guardrails must never trigger API calls."""
        client = DSPyClient(cache_dir=temp_cache_dir)
        mock_context = MagicMock()
        mock_context.to_context_hash.return_value = "hash456"

        with patch.object(client, "_load_cached_prompt") as mock_load:
            mock_load.return_value = None  # Cache miss

            guardrails = client.get_guardrails("test-agent", mock_context)

            # Should only call cache lookup
            mock_load.assert_called_once()

            # Should return default guardrails
            assert len(guardrails) > 0


class TestPromptAuditEntry:
    """Tests for PromptAuditEntry dataclass."""

    def test_create_audit_entry(self):
        """Test creating an audit entry."""
        from dspy_client import PromptAuditEntry

        entry = PromptAuditEntry(
            timestamp="2026-02-14T12:00:00Z",
            context_hash="abc123",
            agent_name="test-agent",
            old_prompt_hash="old123",
            new_prompt_hash="new456",
        )

        assert entry.timestamp == "2026-02-14T12:00:00Z"
        assert entry.context_hash == "abc123"
        assert entry.agent_name == "test-agent"
        assert entry.old_prompt_hash == "old123"
        assert entry.new_prompt_hash == "new456"
        assert entry.schema_version == "1.0.0"

    def test_audit_entry_to_jsonl(self):
        """Test converting audit entry to JSONL."""
        from dspy_client import PromptAuditEntry

        entry = PromptAuditEntry(
            timestamp="2026-02-14T12:00:00Z",
            context_hash="abc123",
            agent_name="test-agent",
            old_prompt_hash=None,
            new_prompt_hash="new456",
        )

        jsonl = entry.to_jsonl()
        data = json.loads(jsonl)

        assert data["timestamp"] == "2026-02-14T12:00:00Z"
        assert data["old_prompt_hash"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
