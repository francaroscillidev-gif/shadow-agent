"""Ultra-fast regex & pattern-based detection and masking engine."""
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from shadow_agent.core.vault import EphemeralVault

@dataclass
class DetectedEntity:
    entity_type: str
    original_value: str
    start: int
    end: int

class MaskingEngine:
    """
    Sub-millisecond regex & rule-based entity detector and masker.
    Supports API Keys, JWT, Emails, IP addresses, Credit Cards, IBANs, and Custom Secrets.
    """
    
    # Pre-compiled high-performance regexes
    PATTERNS = {
        "OPENAI_KEY": re.compile(r"\bsk-(?:proj-|none-)?[a-zA-Z0-9_\-]{32,}\b"),
        "GENERIC_API_KEY": re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key)[\s:='\"]+([a-zA-Z0-9_\-\.]{16,64})"),
        "JWT": re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_\-\.]{10,}\b"),
        "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "IPV4": re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"),
        "CREDIT_CARD": re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b"),
        "IBAN": re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b"),
        "AWS_KEY": re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")
    }

    # Synthetic generators for believable prompt preservation
    SYNTHETIC_COUNTERS: Dict[str, int] = {}

    def __init__(self, use_synthetic: bool = True):
        self.use_synthetic = use_synthetic

    def _generate_synthetic(self, entity_type: str, vault: EphemeralVault) -> str:
        count = len(vault.get_all_mappings()) + 1
        if entity_type == "EMAIL":
            return f"user_{count}@example-sandbox.org"
        elif entity_type in ("OPENAI_KEY", "GENERIC_API_KEY", "AWS_KEY"):
            return f"sk-mock-key-{count}x99999999999999999999"
        elif entity_type == "IPV4":
            return f"10.0.0.{count % 250 + 1}"
        elif entity_type == "CREDIT_CARD":
            return f"400012345678{count:04d}"
        elif entity_type == "IBAN":
            return f"IT00X0000000000000000000{count:03d}"
        elif entity_type == "JWT":
            return f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.synthetic_payload_{count}.mock_signature"
        return f"[[MOCKED_{entity_type}_{count}]]"

    def detect(self, text: str) -> List[DetectedEntity]:
        entities: List[DetectedEntity] = []

        for entity_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(text):
                # If regex has capture group 1 (e.g. for key: "abc..."), extract it
                if match.groups():
                    val = match.group(1)
                    start = match.start(1)
                    end = match.end(1)
                else:
                    val = match.group(0)
                    start = match.start(0)
                    end = match.end(0)

                # Filter out standard non-routable localhost/zeros for IP if desired
                if entity_type == "IPV4" and val in ("0.0.0.0", "127.0.0.1", "255.255.255.255"):
                    continue

                entities.append(DetectedEntity(
                    entity_type=entity_type,
                    original_value=val,
                    start=start,
                    end=end
                ))

        # Sort entities by start index descending so replacement does not shift indices
        entities.sort(key=lambda x: x.start, reverse=True)
        return entities

    def mask(self, text: str, vault: EphemeralVault) -> Tuple[str, List[DetectedEntity]]:
        """Masks detected sensitive data in text, storing mapping in vault."""
        entities = self.detect(text)
        if not entities:
            return text, []

        masked_text = text
        applied_entities = []

        # Avoid overlapping entities
        last_start = len(text) + 1
        for entity in entities:
            if entity.end <= last_start:
                synthetic = self._generate_synthetic(entity.entity_type, vault) if self.use_synthetic else None
                placeholder = vault.get_or_create(entity.original_value, entity.entity_type, synthetic)
                masked_text = masked_text[:entity.start] + placeholder + masked_text[entity.end:]
                last_start = entity.start
                applied_entities.append(entity)

        return masked_text, applied_entities
