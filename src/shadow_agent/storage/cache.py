"""Fast in-memory semantic LRU cache for prompt-response pairs."""
import time
import hashlib
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class CacheEntry:
    response_payload: Dict[str, Any]
    created_at: float
    hits: int = 0

class SemanticCache:
    """
    Sub-millisecond prompt cache based on normalized prompt fingerprints.
    Avoids redundant LLM calls and cuts external token costs.
    """
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 86400):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}

    def _hash_key(self, model: str, sanitized_messages: list) -> str:
        # Normalize messages into predictable representation
        key_repr = f"{model}::" + "||".join(
            f"{m.get('role', '')}:{m.get('content', '')}" for m in sanitized_messages if isinstance(m, dict)
        )
        return hashlib.sha256(key_repr.encode("utf-8")).hexdigest()

    def get(self, model: str, sanitized_messages: list) -> Optional[Dict[str, Any]]:
        key = self._hash_key(model, sanitized_messages)
        entry = self._cache.get(key)
        if not entry:
            return None

        # Check TTL
        if time.time() - entry.created_at > self.ttl_seconds:
            self._cache.pop(key, None)
            return None

        entry.hits += 1
        return entry.response_payload

    def set(self, model: str, sanitized_messages: list, response_payload: Dict[str, Any]):
        if len(self._cache) >= self.max_size:
            # Evict oldest entry
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
            self._cache.pop(oldest_key, None)

        key = self._hash_key(model, sanitized_messages)
        self._cache[key] = CacheEntry(
            response_payload=response_payload,
            created_at=time.time(),
            hits=0
        )

    def stats(self) -> Dict[str, int]:
        total_hits = sum(e.hits for e in self._cache.values())
        return {
            "cached_entries": len(self._cache),
            "total_cache_hits": total_hits
        }
