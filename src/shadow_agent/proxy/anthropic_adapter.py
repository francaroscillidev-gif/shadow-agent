"""
Anthropic Claude Messages API adapter (/v1/messages).
Translates between Anthropic Messages format and internal masking/proxy pipeline.
"""
from typing import Dict, Any, List, Tuple
from shadow_agent.core.vault import EphemeralVault
from shadow_agent.engine.masker import MaskingEngine
from shadow_agent.engine.code_guard import CodeObfuscator
from shadow_agent.engine.injection_guard import InjectionGuard
from shadow_agent.engine.deanonymizer import DeAnonymizer

class AnthropicAdapter:
    """
    Translates Anthropic '/v1/messages' requests into sanitized format,
    and de-anonymizes the Anthropic response choices/stream.
    """
    def __init__(
        self,
        vault: EphemeralVault,
        masker: MaskingEngine,
        code_guard: CodeObfuscator,
        injection_guard: InjectionGuard,
        deanonymizer: DeAnonymizer
    ):
        self.vault = vault
        self.masker = masker
        self.code_guard = code_guard
        self.injection_guard = injection_guard
        self.deanonymizer = deanonymizer

    def sanitize_request(self, body: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Any], List[Any]]:
        """
        Sanitizes an Anthropic payload:
        Anthropic structure: { "model": "...", "messages": [{"role": "user", "content": "..."}], "system": "..." }
        """
        messages = body.get("messages", [])
        system_prompt = body.get("system", "")
        
        total_masked_entities = []
        detected_threats = []
        sanitized_messages = []

        # Sanitize system prompt if present
        sanitized_system = system_prompt
        if isinstance(system_prompt, str) and system_prompt:
            is_threat, _, threats = self.injection_guard.scan(system_prompt)
            if is_threat:
                detected_threats.extend(threats)
            sanitized_system, entities = self.masker.mask(system_prompt, self.vault)
            total_masked_entities.extend(entities)

        # Sanitize messages
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                is_threat, _, threats = self.injection_guard.scan(content)
                if is_threat:
                    detected_threats.extend(threats)

                masked, entities = self.masker.mask(content, self.vault)
                total_masked_entities.extend(entities)

                masked, code_entities = self.code_guard.detect_and_mask(masked, self.vault)
                total_masked_entities.extend(code_entities)

                sanitized_messages.append({**msg, "content": masked})
            elif isinstance(content, list):
                sanitized_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_val = part.get("text", "")
                        is_threat, _, threats = self.injection_guard.scan(text_val)
                        if is_threat:
                            detected_threats.extend(threats)

                        masked, entities = self.masker.mask(text_val, self.vault)
                        total_masked_entities.extend(entities)
                        masked, code_entities = self.code_guard.detect_and_mask(masked, self.vault)
                        total_masked_entities.extend(code_entities)

                        sanitized_parts.append({**part, "text": masked})
                    else:
                        sanitized_parts.append(part)
                sanitized_messages.append({**msg, "content": sanitized_parts})
            else:
                sanitized_messages.append(msg)

        forward_body = {
            **body,
            "system": sanitized_system,
            "messages": sanitized_messages
        }

        return forward_body, total_masked_entities, detected_threats

    def restore_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restores placeholders in Anthropic response content blocks."""
        if "content" in response_data and isinstance(response_data["content"], list):
            for block in response_data["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    block["text"] = self.deanonymizer.restore_batch(block.get("text", ""))
        return response_data
