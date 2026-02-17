#!/usr/bin/env python3
"""
DSPy client for multi-review prompt calibration.

This module provides the DSPy client for Layer 1 prompt calibration.
CRITICAL: The API takes 30+ seconds which is unacceptable for interactive use.
Therefore, this client uses FAIL-CLOSED caching - the API is NEVER called
during runtime; only cache lookups or pre-compiled defaults are used.

Cache Strategy (FAIL-CLOSED):
1. Pre-compile at plugin install time (generate common scenarios)
2. Hash lookup at runtime (~1ms)
3. context_hash = SHA256(config + schema_version + filter_version)
4. TTL: 7 days BUT invalidate on content hash change
5. Cache integrity: Verify sha256 on read
6. Manual refresh: --refresh-cache command (explicit, user-initiated)
7. API NEVER in runtime path

Dependencies:
    - Python 3.10+ stdlib only (for core functionality)
    - requests (optional, only for --refresh-cache)
"""

import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from project_context import ProjectContext

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Cache configuration
CACHE_DIR_NAME = "optimized-prompts"
DEFAULT_TTL_DAYS = 7

# API configuration (for --refresh-cache only)
DEFAULT_API_URL = "http://localhost:8000/api/v1/improve-prompt"
DEFAULT_API_TIMEOUT = 60  # seconds
DEFAULT_API_MODE = "legacy"  # Use 'legacy' mode (stable, produces correct guardrails)

# Audit log configuration
AUDIT_LOG_NAME = "audit_log.jsonl"


# =============================================================================
# CACHE DATACLASS
# =============================================================================


@dataclass
class CachedPrompt:
    """A cached calibrated prompt.

    Attributes:
        context_hash: Hash of the context that generated this prompt.
        agent_name: Name of the agent this prompt is for.
        calibrated_prompt: The calibrated prompt text.
        guardrails: List of guardrail strings.
        created_at: ISO timestamp of when this was cached.
        ttl_days: Time-to-live in days.
        integrity_hash: SHA256 of (prompt + guardrails) for integrity check.
    """

    context_hash: str
    agent_name: str
    calibrated_prompt: str
    guardrails: List[str]
    created_at: str
    ttl_days: int = DEFAULT_TTL_DAYS
    integrity_hash: Optional[str] = None

    def __post_init__(self) -> None:
        """Calculate integrity hash if not set."""
        if self.integrity_hash is None:
            content = self.calibrated_prompt + "".join(self.guardrails)
            self.integrity_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    def is_expired(self) -> bool:
        """Check if this cached prompt has expired.

        Returns:
            True if the TTL has passed.
        """
        try:
            created = datetime.fromisoformat(self.created_at)
            expires_at = created + timedelta(days=self.ttl_days)
            return datetime.now() > expires_at
        except (ValueError, TypeError):
            return True  # Invalid date = expired

    def verify_integrity(self) -> bool:
        """Verify the integrity hash matches.

        Returns:
            True if integrity check passes.
        """
        content = self.calibrated_prompt + "".join(self.guardrails)
        expected = hashlib.sha256(content.encode()).hexdigest()[:16]
        return self.integrity_hash == expected

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CachedPrompt":
        """Create from dictionary."""
        return cls(**data)


# =============================================================================
# AUDIT LOG ENTRY
# =============================================================================


@dataclass
class PromptAuditEntry:
    """Audit entry for prompt cache refresh operations.

    This enables tracking of cache refresh operations for:
    - Reproducibility (know when prompts were updated)
    - Debugging (trace prompt changes)
    - Compliance (audit trail of API calls)

    Attributes:
        timestamp: ISO timestamp of the refresh operation.
        context_hash: Hash of the context for this prompt.
        agent_name: Name of the agent.
        old_prompt_hash: Hash of the previous prompt (None if new).
        new_prompt_hash: Hash of the new prompt.
        schema_version: Version of the audit entry schema.
        model: Model used for calibration (e.g., 'claude-sonnet-4.5').
    """

    timestamp: str
    context_hash: str
    agent_name: str
    old_prompt_hash: Optional[str]
    new_prompt_hash: str
    schema_version: str = "1.0.0"
    model: str = "claude-sonnet-4.5"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_jsonl(self) -> str:
        """Convert to JSONL format (single line JSON)."""
        return json.dumps(self.to_dict())


# =============================================================================
# DEFAULT PROMPTS (Pre-compiled)
# =============================================================================

DEFAULT_PROMPTS: Dict[str, Dict[str, Any]] = {
    "feature-dev:code-reviewer": {
        "calibrated_prompt": """Review the code changes with confidence-based filtering.

Focus on:
- Security vulnerabilities
- Logic errors and bugs
- Performance issues
- Missing error handling (NOT covered by existing tools)

Skip:
- Style/formatting issues (handled by ruff/black)
- Type annotation gaps (handled by mypy)
- Nitpicks and optional enhancements

OUTPUT FORMAT - Use XML tags for each finding:

<finding id="1" confidence="75" severity="Important">
  <file>src/auth.py</file>
  <line>45</line>
  <category>security</category>
  <description>Brief description of the issue</description>
  <evidence>
    <ref tool="code-review">Why this is an issue</ref>
  </evidence>
  <suggested_fix>How to fix it</suggested_fix>
</finding>

Confidence Scoring Guide:
- 0: False positive or pre-existing issue
- 25: Low - might be real but likely nitpick
- 50: Medium - verified real but rarely hit
- 75: High - very likely real and commonly hit
- 100: Certain - directly confirmed, frequently encountered""",
        "guardrails": [
            "1. Do not flag issues already caught by configured linters",
            "2. Focus on critical domains: auth, payments, data integrity",
            "3. Only recommend tests for uncovered scenarios",
        ],
    },
    "pr-review-toolkit:silent-failure-hunter": {
        "calibrated_prompt": """Hunt for silent failures and inadequate error handling.

Focus on:
- Caught exceptions with empty handlers
- Fallback logic that silently ignores errors
- Missing error propagation
- Graceful degradation without logging

Skip:
- Error handling covered by shell strict mode (set -euo pipefail)
- Intentional silent failures with clear comments
- Error handling in test fixtures

OUTPUT FORMAT - Use XML tags for each finding:

<finding id="1" confidence="75" severity="Important">
  <file>src/api.py</file>
  <line>128</line>
  <category>error_handling</category>
  <description>Description of silent failure</description>
  <evidence>
    <ref tool="silent-failure-hunter">Why this is problematic</ref>
  </evidence>
  <suggested_fix>How to add proper error handling</suggested_fix>
</finding>

Confidence Scoring Guide:
- 0: False positive or intentional design
- 25: Low - might be issue but acceptable
- 50: Medium - real gap but low impact
- 75: High - definite gap with real impact
- 100: Certain - critical silent failure""",
        "guardrails": [
            "1. Only flag genuine error-handling gaps",
            "2. Distinguish between silent failures and handled fallbacks",
            "3. Consider context: is silent failure intentional?",
        ],
    },
    "pr-review-toolkit:pr-test-analyzer": {
        "calibrated_prompt": """Analyze test coverage quality and completeness.

Focus on:
- Missing test coverage for critical paths
- Edge cases not tested
- Test quality issues (flaky, incomplete assertions)
- Missing integration tests for API endpoints

Skip:
- Tests for trivial getters/setters
- 100% coverage requirements for internal helpers
- Style issues in test files

OUTPUT FORMAT - Use XML tags for each finding:

<finding id="1" confidence="75" severity="Important">
  <file>tests/user_test.py</file>
  <line>45</line>
  <category>test_coverage</category>
  <description>Missing test for X scenario</description>
  <evidence>
    <ref tool="pr-test-analyzer">Why this test matters</ref>
  </evidence>
  <suggested_fix>Add test case for X</suggested_fix>
</finding>

Confidence Scoring Guide:
- 0: Not a coverage gap
- 25: Low - nice to have test
- 50: Medium - real gap but low risk
- 75: High - critical path untested
- 100: Certain - security/critical path has no coverage""",
        "guardrails": [
            "1. Focus on critical domains: auth, payments, data",
            "2. Only recommend tests for actual coverage gaps",
            "3. Consider test value vs implementation effort",
        ],
    },
    "pr-review-toolkit:type-design-analyzer": {
        "calibrated_prompt": """Analyze type design quality and invariants.

Focus on:
- Missing or incorrect type annotations
- Weak type definitions (too permissive)
- Invariant violations
- Runtime type safety issues

Skip:
- Type annotations in internal helpers (if not strict mode)
- Optional type enhancements (could use Literal, etc.)
- Style issues in type definitions

OUTPUT FORMAT - Use XML tags for each finding:

<finding id="1" confidence="75" severity="Important">
  <file>src/models.py</file>
  <line>23</line>
  <category>type_design</category>
  <description>Type invariant violation</description>
  <evidence>
    <ref tool="type-design-analyzer">Why this matters</ref>
  </evidence>
  <suggested_fix>Strengthen type definition</suggested_fix>
</finding>

Confidence Scoring Guide:
- 0: Not a type issue
- 25: Low - optional enhancement
- 50: Medium - real weakness but low impact
- 75: High - type safety risk
- 100: Certain - runtime error possible""",
        "guardrails": [
            "1. Focus on types that affect correctness",
            "2. Consider project's type checking strictness",
            "3. Only flag issues that would cause runtime errors",
        ],
    },
    "pr-review-toolkit:code-simplifier": {
        "calibrated_prompt": """Simplify code for clarity and maintainability.

Focus on:
- Dead code removal
- Duplicate code consolidation
- Overly complex conditionals
- Unnecessary abstractions

Skip:
- Working code that is already clear
- Complex code that is justified by requirements
- Refactoring that changes behavior

OUTPUT FORMAT - Use XML tags for each finding:

<finding id="1" confidence="50" severity="Low">
  <file>src/utils.py</file>
  <line>112</line>
  <category>complexity</category>
  <description>Function can be simplified</description>
  <evidence>
    <ref tool="code-simplifier">Why simplification helps</ref>
  </evidence>
  <suggested_fix>Extract to helper function</suggested_fix>
</finding>

Confidence Scoring Guide:
- 0: Code is fine as-is
- 25: Low - minor improvement possible
- 50: Medium - noticeable complexity
- 75: High - significant maintainability issue
- 100: Certain - critical complexity blocking work""",
        "guardrails": [
            "1. Only simplify if it improves clarity",
            "2. Preserve all functionality",
            "3. Consider future maintenance cost",
        ],
    },
}


def get_default_prompt(agent_name: str) -> Dict[str, Any]:
    """Get default pre-compiled prompt for an agent.

    Args:
        agent_name: Name of the agent.

    Returns:
        Dictionary with 'calibrated_prompt' and 'guardrails'.
    """
    if agent_name in DEFAULT_PROMPTS:
        return DEFAULT_PROMPTS[agent_name]

    # Generic fallback
    return {
        "calibrated_prompt": """Review the code changes with confidence-based filtering.

Provide findings with:
- Severity: Critical/Important/Low
- Confidence: 0-100
- File and line numbers
- Brief description and suggested fix

Focus on actionable issues, not nitpicks.

OUTPUT FORMAT - Use XML tags for each finding:

<finding id="1" confidence="75" severity="Important">
  <file>src/file.py</file>
  <line>42</line>
  <category>general</category>
  <description>Description of the issue</description>
  <evidence>
    <ref tool="review">Why this is an issue</ref>
  </evidence>
  <suggested_fix>How to fix it</suggested_fix>
</finding>

Confidence Scoring Guide:
- 0: False positive
- 25: Low - might be real but nitpick
- 50: Medium - verified real, rarely hit
- 75: High - very likely real
- 100: Certain - directly confirmed""",
        "guardrails": [
            "1. Focus on critical issues",
            "2. Provide actionable recommendations",
            "3. Use confidence scoring appropriately",
        ],
    }


# =============================================================================
# DSPY CLIENT CLASS
# =============================================================================


class DSPyClient:
    """Client for DSPy prompt calibration with FAIL-CLOSED caching.

    CRITICAL: The DSPy API takes 30+ seconds which is unacceptable for
    interactive use. Therefore, this client NEVER calls the API during
    runtime. It only uses:
    1. Cache lookups (~1ms)
    2. Pre-compiled default prompts

    API calls are ONLY made during explicit --refresh-cache operations.

    Example:
        >>> client = DSPyClient()
        >>> prompt = client.build_review_prompt("code-reviewer", context)
        >>> # Returns from cache or default - NEVER waits for API
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ):
        """Initialize the DSPy client.

        Args:
            cache_dir: Directory for cache files (defaults to plugin resources).
            ttl_days: Cache time-to-live in days.
        """
        if cache_dir is None:
            # Default to plugin resources directory
            cache_dir = Path(__file__).parent.parent / "resources" / CACHE_DIR_NAME

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days
        self._audit_log_path = self.cache_dir / AUDIT_LOG_NAME

    def _append_audit_entry(self, entry: PromptAuditEntry) -> bool:
        """Append an entry to the audit log.

        Args:
            entry: The audit entry to append.

        Returns:
            True if append was successful.
        """
        try:
            # Append to JSONL file
            with open(self._audit_log_path, "a", encoding="utf-8") as f:
                f.write(entry.to_jsonl() + "\n")
            logger.debug(f"Appended audit entry for {entry.agent_name}")
            return True
        except OSError as e:
            logger.warning(f"Failed to append audit entry: {e}")
            return False

    def _get_prompt_hash(self, prompt: str) -> str:
        """Get hash of a prompt for audit tracking.

        Args:
            prompt: The prompt text.

        Returns:
            16-character hash string.
        """
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    def _hash_context(self, agent_name: str, context: "ProjectContext") -> str:
        """Generate hash for cache lookup.

        The hash includes:
        - Agent name
        - Context hash (which includes schema + config + filter versions)

        Args:
            agent_name: Name of the agent.
            context: Project context.

        Returns:
            32-character hex string (truncated SHA256).
        """
        content = f"{agent_name}:{context.to_context_hash()}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_cache_path(self, context_hash: str) -> Path:
        """Get cache file path for a context hash.

        Args:
            context_hash: The context hash.

        Returns:
            Path to the cache file.
        """
        return self.cache_dir / f"{context_hash}.json"

    def _load_cached_prompt(self, context_hash: str) -> Optional[CachedPrompt]:
        """Load cached prompt from disk.

        Args:
            context_hash: The context hash to look up.

        Returns:
            CachedPrompt if found and valid, None otherwise.
        """
        cache_path = self._get_cache_path(context_hash)

        if not cache_path.exists():
            return None

        try:
            content = cache_path.read_text(encoding="utf-8")
            data = json.loads(content)
            cached = CachedPrompt.from_dict(data)

            # Verify integrity
            if not cached.verify_integrity():
                logger.warning(
                    f"Cache integrity check failed for {context_hash}, "
                    "file may be corrupted"
                )
                return None

            return cached

        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Failed to load cache for {context_hash}: {e}")
            return None

    def _save_cached_prompt(self, cached: CachedPrompt) -> bool:
        """Save cached prompt to disk.

        Args:
            cached: The cached prompt to save.

        Returns:
            True if save was successful.
        """
        cache_path = self._get_cache_path(cached.context_hash)

        try:
            content = json.dumps(cached.to_dict(), indent=2)
            cache_path.write_text(content, encoding="utf-8")
            logger.info(f"Saved cached prompt to {cache_path}")
            return True

        except (OSError, TypeError) as e:
            logger.error(f"Failed to save cache: {e}")
            return False

    def build_review_prompt(
        self,
        agent_name: str,
        context: "ProjectContext",
    ) -> str:
        """Build context-aware review prompt - ALWAYS from cache.

        This method NEVER calls the API. It returns:
        1. Cached prompt if available and valid (~1ms)
        2. Pre-compiled default prompt if cache miss

        Args:
            agent_name: Name of the agent (e.g., 'feature-dev:code-reviewer').
            context: Project context for calibration.

        Returns:
            Calibrated prompt string.
        """
        context_hash = self._hash_context(agent_name, context)

        # Check cache first (O(1) lookup, ~1ms)
        cached = self._load_cached_prompt(context_hash)
        if cached and not cached.is_expired():
            logger.debug(f"Using cached prompt for {agent_name}")
            return cached.calibrated_prompt

        # Cache miss or expired - use pre-compiled default
        # API call is TOO SLOW (30s) for interactive use
        logger.debug(f"Using default prompt for {agent_name} (cache miss)")
        default = get_default_prompt(agent_name)
        return default["calibrated_prompt"]

    def get_guardrails(
        self,
        agent_name: str,
        context: "ProjectContext",
    ) -> List[str]:
        """Get calibrated guardrails for an agent.

        Args:
            agent_name: Name of the agent.
            context: Project context.

        Returns:
            List of guardrail strings.
        """
        context_hash = self._hash_context(agent_name, context)

        # Check cache
        cached = self._load_cached_prompt(context_hash)
        if cached and not cached.is_expired():
            return cached.guardrails

        # Use default
        default = get_default_prompt(agent_name)
        return default["guardrails"]

    def precompile_prompts(
        self,
        agents: List[str],
        contexts: List["ProjectContext"],
    ) -> Dict[str, bool]:
        """Pre-compile prompts for common scenarios.

        This should be run at plugin install time or in the background.
        It generates cache files for common context combinations.

        Args:
            agents: List of agent names to pre-compile for.
            contexts: List of context scenarios to pre-compile.

        Returns:
            Dictionary mapping agent:context_hash to success status.
        """
        results = {}

        for agent_name in agents:
            for context in contexts:
                context_hash = self._hash_context(agent_name, context)

                # Get default as base
                default = get_default_prompt(agent_name)

                # Create cached entry
                cached = CachedPrompt(
                    context_hash=context_hash,
                    agent_name=agent_name,
                    calibrated_prompt=default["calibrated_prompt"],
                    guardrails=default["guardrails"],
                    created_at=datetime.now().isoformat(),
                    ttl_days=self.ttl_days,
                )

                success = self._save_cached_prompt(cached)
                results[f"{agent_name}:{context_hash[:8]}"] = success

        return results

    def refresh_from_api(
        self,
        agent_name: str,
        context: "ProjectContext",
        api_url: str = DEFAULT_API_URL,
        api_timeout: int = DEFAULT_API_TIMEOUT,
        mode: str = DEFAULT_API_MODE,
    ) -> Optional[str]:
        """Refresh prompt from API (EXPLICIT user action only).

        WARNING: This takes 30+ seconds. Only call for --refresh-cache.

        Args:
            agent_name: Name of the agent.
            context: Project context.
            api_url: DSPy API URL.
            api_timeout: API timeout in seconds.
            mode: API mode ('legacy' or 'nlac').

        Returns:
            Calibrated prompt string, or None on failure.
        """
        try:
            import requests
        except ImportError:
            logger.error("requests library not installed - cannot call API")
            return None

        context_hash = self._hash_context(agent_name, context)

        # Get old prompt hash for audit (if exists)
        old_cached = self._load_cached_prompt(context_hash)
        old_prompt_hash = None
        if old_cached:
            old_prompt_hash = self._get_prompt_hash(old_cached.calibrated_prompt)

        # Build request
        payload = {
            "prompt": f"Review prompt for {agent_name}",
            "mode": mode,
            "context": {
                "agent_name": agent_name,
                "project_context": context.to_dict(),
            },
        }

        try:
            logger.info(
                f"Calling DSPy API for {agent_name} (this takes 30+ seconds)..."
            )
            response = requests.post(
                api_url,
                json=payload,
                timeout=api_timeout,
            )
            response.raise_for_status()

            data = response.json()
            calibrated_prompt = data.get("calibrated_prompt", "")
            guardrails = data.get("guardrails", [])

            # Cache the result
            cached = CachedPrompt(
                context_hash=context_hash,
                agent_name=agent_name,
                calibrated_prompt=calibrated_prompt,
                guardrails=guardrails,
                created_at=datetime.now().isoformat(),
                ttl_days=self.ttl_days,
            )
            self._save_cached_prompt(cached)

            # Create audit entry
            new_prompt_hash = self._get_prompt_hash(calibrated_prompt)
            audit_entry = PromptAuditEntry(
                timestamp=datetime.now().isoformat(),
                context_hash=context_hash,
                agent_name=agent_name,
                old_prompt_hash=old_prompt_hash,
                new_prompt_hash=new_prompt_hash,
                model="claude-sonnet-4.5",  # Default model
            )
            self._append_audit_entry(audit_entry)

            logger.info(f"Successfully refreshed prompt for {agent_name}")
            return calibrated_prompt

        except requests.Timeout:
            logger.error(f"API call timed out after {api_timeout} seconds")
            return None
        except requests.RequestException as e:
            logger.error(f"API call failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during API call: {e}")
            return None

    def clear_cache(self) -> int:
        """Clear all cached prompts.

        Returns:
            Number of cache files deleted.
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError as e:
                logger.warning(f"Failed to delete {cache_file}: {e}")

        logger.info(f"Cleared {count} cached prompts")
        return count

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache.

        Returns:
            Dictionary with cache statistics.
        """
        cache_files = list(self.cache_dir.glob("*.json"))
        valid = 0
        expired = 0
        corrupted = 0

        for cache_file in cache_files:
            try:
                content = cache_file.read_text(encoding="utf-8")
                data = json.loads(content)
                cached = CachedPrompt.from_dict(data)

                if not cached.verify_integrity():
                    corrupted += 1
                elif cached.is_expired():
                    expired += 1
                else:
                    valid += 1

            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                corrupted += 1

        return {
            "total_files": len(cache_files),
            "valid": valid,
            "expired": expired,
            "corrupted": corrupted,
            "cache_dir": str(self.cache_dir),
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_calibrated_prompt(
    agent_name: str,
    context: "ProjectContext",
) -> str:
    """Get calibrated prompt for an agent (convenience function).

    This is the main entry point for getting prompts. It handles
    caching and defaults automatically.

    Args:
        agent_name: Name of the agent.
        context: Project context.

    Returns:
        Calibrated prompt string (from cache or default).
    """
    client = DSPyClient()
    return client.build_review_prompt(agent_name, context)
