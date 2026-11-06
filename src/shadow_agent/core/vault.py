"""High performance in-memory ephemeral vault for bi-directional token mapping."""
import time
import secrets
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field

@dataclass
class VaultEntry:
    original_value: str
    placeholder: str
    entity_type: str
    created_at: float = field(default_factory=time.time)

class EphemeralVault:
    """
    Thread-safe session-scoped or global ephemeral vault.
    Maps placeholders to original sensitive values with auto-expiration (TTL).
    """
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        # Maps placeholder -> VaultEntry
        self._placeholder_to_original: Dict[str, VaultEntry] = {}
        # Maps original_value -> placeholder (for deterministic replacement within session)
        self._original_to_placeholder: Dict[str, str] = {}

    def get_or_create(self, original_value: str, entity_type: str, synthetic_value: Optional[str] = None) -> str:
        self.clean_expired()
        
        if original_value in self._original_to_placeholder:
            return self._original_to_placeholder[original_value]
        
        if synthetic_value:
            placeholder = synthetic_value
        else:
            token_id = secrets.token_hex(4).upper()
            placeholder = f"[[PROTECTED_{entity_type}_{token_id}]]"
        
        # In case of duplicate synthetic value collision
        if placeholder in self._placeholder_to_original:
            token_id = secrets.token_hex(4).upper()
            placeholder = f"[[PROTECTED_{entity_type}_{token_id}]]"

        entry = VaultEntry(
            original_value=original_value,
            placeholder=placeholder,
            entity_type=entity_type
        )
        self._placeholder_to_original[placeholder] = entry
        self._original_to_placeholder[original_value] = placeholder
        return placeholder

    def get_original(self, placeholder: str) -> Optional[str]:
        self.clean_expired()
        entry = self._placeholder_to_original.get(placeholder)
        return entry.original_value if entry else None

    def get_all_mappings(self) -> Dict[str, str]:
        """Returns dict of {placeholder: original_value}"""
        self.clean_expired()
        return {k: v.original_value for k, v in self._placeholder_to_original.items()}

    def clean_expired(self):
        now = time.time()
        expired_keys = [
            k for k, v in self._placeholder_to_original.items()
            if now - v.created_at > self.ttl_seconds
        ]
        for k in expired_keys:
            entry = self._placeholder_to_original.pop(k, None)
            if entry and entry.original_value in self._original_to_placeholder:
                self._original_to_placeholder.pop(entry.original_value, None)

    def clear(self):
        self._placeholder_to_original.clear()
        self._original_to_placeholder.clear()
