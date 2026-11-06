"""AST and code-aware tokenizer to mask internal database schemas and proprietary table/column names."""
import re
from typing import List, Tuple
from shadow_agent.core.vault import EphemeralVault
from shadow_agent.engine.masker import DetectedEntity

class CodeObfuscator:
    """
    Detects and masks internal database connection strings, table identifiers,
    and sensitive SQL/schema definitions inside code snippets before sending to LLMs.
    """
    
    PATTERNS = {
        "DB_URI": re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|sqlite)://[a-zA-Z0-9_\-\.]+:[^@\s]+@[a-zA-Z0-9_\-\.]+:[0-9]+/[a-zA-Z0-9_\-\.]+\b"),
        "SQL_PASSWORD": re.compile(r"(?i)\b(?:password|pwd|secret)[\s]*=[\s]*['\"][^'\"]{6,}['\"]"),
        "INTERNAL_SCHEMA_TABLE": re.compile(r"(?i)\b(?:from|join|into|update)\s+([a-zA-Z0-9_]{3,30}_(?:prod|secrets|finance|auth|billing))\b")
    }

    def __init__(self, use_synthetic: bool = True):
        self.use_synthetic = use_synthetic

    def detect_and_mask(self, code_text: str, vault: EphemeralVault) -> Tuple[str, List[DetectedEntity]]:
        entities: List[DetectedEntity] = []

        for entity_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(code_text):
                if match.groups():
                    val = match.group(1)
                    start = match.start(1)
                    end = match.end(1)
                else:
                    val = match.group(0)
                    start = match.start(0)
                    end = match.end(0)

                entities.append(DetectedEntity(
                    entity_type=entity_type,
                    original_value=val,
                    start=start,
                    end=end
                ))

        if not entities:
            return code_text, []

        entities.sort(key=lambda x: x.start, reverse=True)
        masked_text = code_text
        applied_entities = []
        last_start = len(code_text) + 1

        for entity in entities:
            if entity.end <= last_start:
                if entity.entity_type == "DB_URI":
                    synthetic = "postgresql://mock_user:mock_pass@127.0.0.1:5432/mock_db"
                elif entity.entity_type == "SQL_PASSWORD":
                    synthetic = 'password="synthetic_safe_pwd_123"'
                elif entity.entity_type == "INTERNAL_SCHEMA_TABLE":
                    synthetic = f"mock_{entity.original_value.split('_')[-1]}_table"
                else:
                    synthetic = f"[[MOCKED_{entity.entity_type}]]"

                placeholder = vault.get_or_create(entity.original_value, entity.entity_type, synthetic if self.use_synthetic else None)
                masked_text = masked_text[:entity.start] + placeholder + masked_text[entity.end:]
                last_start = entity.start
                applied_entities.append(entity)

        return masked_text, applied_entities
