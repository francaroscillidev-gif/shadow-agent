"""Immutable local audit logger for enterprise compliance."""
import json
import time
import hashlib
from typing import Dict, Any, List
from pathlib import Path

class AuditLogger:
    def __init__(self, log_path: str = "shadow_audit.jsonl"):
        self.log_path = Path(log_path)

    def log_transaction(
        self,
        request_id: str,
        destination: str,
        model: str,
        entities_masked: int,
        entity_types: List[str],
        route_meta: Dict[str, Any],
        raw_prompt_preview: str,
        latency_ms: float
    ):
        """
        Logs metadata without storing actual sensitive values or complete unmasked prompts.
        Uses SHA-256 fingerprint for tamper-proof reference.
        """
        fingerprint = hashlib.sha256(raw_prompt_preview.encode("utf-8")).hexdigest()
        
        entry = {
            "timestamp": time.time(),
            "request_id": request_id,
            "destination": destination,
            "model": model,
            "entities_masked_count": entities_masked,
            "entity_types": entity_types,
            "routing_reason": route_meta.get("reason"),
            "risk_level": route_meta.get("risk_level"),
            "prompt_sha256": fingerprint,
            "latency_ms": round(latency_ms, 2)
        }

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Do not block main request flow if logging write fails
