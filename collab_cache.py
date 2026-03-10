"""
collab_cache.py — Redis caching layer for ScleraCollab

Configuration (set in .env or environment):
    REDIS_URL        Full URL e.g. redis://localhost:6379 or
                     rediss://:<token>@<host>.upstash.io:6380  (Upstash / Redis Cloud)
    REDIS_HOST       Fallback hostname  (default: localhost)
    REDIS_PORT       Fallback port      (default: 6379)

If Redis is unavailable at startup, every cache call silently no-ops so the
rest of the app continues working — just without caching.

TTLs (seconds):
    FEED_TTL          = 300   (5 minutes)
    USER_PROFILE_TTL  = 3600  (1 hour)
    POST_ANALYSIS_TTL = 86400 (24 hours)
    TRENDING_TTL      = 600   (10 minutes)
"""

import os
import json
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── TTL constants ─────────────────────────────────────────────────────────────
FEED_TTL          = 300    # 5 min  — feed ranked list per user
USER_PROFILE_TTL  = 3600   # 1 hr   — interest profile per user
POST_ANALYSIS_TTL = 86400  # 24 hrs — post NLP analysis
TRENDING_TTL      = 600    # 10 min — trending hashtags

# ── Connection state ──────────────────────────────────────────────────────────
_redis           = None       # live client once connected
_last_fail_time  = None       # monotonic timestamp of last connection failure
_RETRY_COOLDOWN  = 30         # seconds to wait before retrying after a failure


def _connect() -> Optional[object]:
    """Attempt to create and ping a Redis connection.

    Cooldown design: after any failure we set _last_fail_time and refuse
    to retry for _RETRY_COOLDOWN seconds.  This means:
    - Redis is down at startup  → 1 warning logged, then silence for 30 s.
    - Redis drops mid-session   → 1 warning per 30 s, not per cache call.
    - No repeated DNS lookups   → page load is not slowed by 16 failed
      getaddrinfo() calls.
    """
    global _redis, _last_fail_time

    # Already connected
    if _redis is not None:
        return _redis

    # Still within cooldown after last failure — skip immediately
    if _last_fail_time is not None:
        if time.monotonic() - _last_fail_time < _RETRY_COOLDOWN:
            return None

    # Attempt connection
    try:
        import redis as redis_lib
        url = os.environ.get('REDIS_URL')
        if url:
            client = redis_lib.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        else:
            host = os.environ.get('REDIS_HOST', 'localhost')
            port = int(os.environ.get('REDIS_PORT', 6379))
            client = redis_lib.Redis(
                host=host, port=port, db=0,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        client.ping()          # single ping at connection time only
        _redis          = client
        _last_fail_time = None
        logger.info('✅ Redis connected')
    except Exception as e:
        _last_fail_time = time.monotonic()
        logger.warning(f'⚠️  Redis unavailable — caching disabled ({e})')
        _redis = None

    return _redis


def _client() -> Optional[object]:
    """Return live Redis client or None — no per-call ping."""
    return _connect()


def _on_error(e: Exception, context: str = ''):
    """Called when a Redis command fails mid-session.  Resets state so the
    next call will attempt reconnection (after cooldown)."""
    global _redis, _last_fail_time
    _redis          = None
    _last_fail_time = time.monotonic()
    logger.debug(f'Redis command error{" [" + context + "]" if context else ""}: {e}')


# ── Key helpers ───────────────────────────────────────────────────────────────

def _feed_key(uid: str, cursor: str = '') -> str:
    return f'feed:{uid}:{cursor or "start"}'

def _profile_key(uid: str) -> str:
    return f'user_profile:{uid}'

def _analysis_key(post_id: str) -> str:
    return f'post_analysis:{post_id}'

def _trending_key() -> str:
    return 'trending:hashtags'


# ── Generic get / set / delete ────────────────────────────────────────────────

def cache_get(key: str):
    """Return deserialized value or None on miss / error."""
    r = _client()
    if r is None:
        return None
    try:
        raw = r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as e:
        _on_error(e, f'GET {key}')
        return None


def cache_set(key: str, value, ttl: int = 300) -> bool:
    """Serialize and store value with TTL. Returns True on success."""
    r = _client()
    if r is None:
        return False
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
        return True
    except Exception as e:
        _on_error(e, f'SET {key}')
        return False


def cache_delete(key: str) -> bool:
    r = _client()
    if r is None:
        return False
    try:
        r.delete(key)
        return True
    except Exception as e:
        _on_error(e, f'DEL {key}')
        return False


def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern. Returns count deleted."""
    r = _client()
    if r is None:
        return 0
    try:
        keys = r.keys(pattern)
        if keys:
            return r.delete(*keys)
        return 0
    except Exception as e:
        _on_error(e, f'DEL pattern {pattern}')
        return 0


# ── Domain-specific helpers ───────────────────────────────────────────────────

def get_feed_cache(uid: str, cursor: str = '') -> Optional[dict]:
    return cache_get(_feed_key(uid, cursor))


def set_feed_cache(uid: str, cursor: str, data: dict) -> bool:
    return cache_set(_feed_key(uid, cursor), data, FEED_TTL)


def invalidate_user_feed_cache(uid: str):
    """Delete all feed pages for a user (called on new post / react / comment)."""
    cache_delete_pattern(f'feed:{uid}:*')


def invalidate_feed_for_connections(uid: str, connected_uids: list):
    """
    When uid creates a post, their connections' feeds may become stale too.
    We invalidate their caches so they see the new post within 5 minutes
    without waiting for TTL expiry.
    """
    invalidate_user_feed_cache(uid)
    for cuid in connected_uids:
        invalidate_user_feed_cache(cuid)


def get_post_analysis_cache(post_id: str) -> Optional[dict]:
    return cache_get(_analysis_key(post_id))


def set_post_analysis_cache(post_id: str, analysis: dict) -> bool:
    # Never cache the embedding in Redis — it's large (384 floats).
    # Keep only the lightweight fields.
    slim = {k: v for k, v in analysis.items() if k != 'semantic_embedding'}
    return cache_set(_analysis_key(post_id), slim, POST_ANALYSIS_TTL)


def get_user_profile_cache(uid: str) -> Optional[dict]:
    return cache_get(_profile_key(uid))


def set_user_profile_cache(uid: str, profile: dict) -> bool:
    # Also strip embedding before storing (can be large)
    slim = {k: v for k, v in profile.items() if k != 'embedding'}
    return cache_set(_profile_key(uid), slim, USER_PROFILE_TTL)


def invalidate_user_profile_cache(uid: str):
    cache_delete(_profile_key(uid))


def get_trending_cache() -> Optional[list]:
    return cache_get(_trending_key())


def set_trending_cache(data: list) -> bool:
    return cache_set(_trending_key(), data, TRENDING_TTL)


# ── Startup probe ─────────────────────────────────────────────────────────────

def probe() -> bool:
    """Call once at app startup to log Redis status."""
    return _client() is not None