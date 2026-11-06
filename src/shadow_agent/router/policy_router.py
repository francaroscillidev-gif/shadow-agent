"""Intelligent router that inspects prompt sensitivity, complexity, and directs queries."""
from typing import Dict, Any, Tuple
from shadow_agent.core.config import ServerConfig

class Router:
    """
    Decides whether a request should be dispatched to:
    1. Local LLM (Ollama/vLLM) -> Sensitive, air-gapped, zero data leaves local network.
    2. Cloud LLM (Gemini/OpenAI/Claude) -> High complexity, sanitized via masking proxy.
    """
    def __init__(self, config: ServerConfig):
        self.config = config

    def inspect_and_route(self, messages: list, sensitive_count: int) -> Tuple[str, str, Dict[str, Any]]:
        """
        Returns:
            (target_destination, chosen_model, route_metadata)
            target_destination is either 'local' or 'cloud'
        """
        full_prompt = " ".join([m.get("content", "") for m in messages if isinstance(m.get("content"), str)])
        full_prompt_lower = full_prompt.lower()

        # Check for strict air-gap keywords
        for keyword in self.config.privacy.force_local_keywords:
            if keyword.lower() in full_prompt_lower:
                return (
                    "local",
                    self.config.upstream.local_default_model,
                    {"reason": f"Triggered by air-gap keyword: '{keyword}'", "risk_level": "CRITICAL"}
                )

        # Check if sensitive items exceed threshold or unmaskable
        if self.config.privacy.auto_route_to_local_if_unmaskable and sensitive_count > 10:
            return (
                "local",
                self.config.upstream.local_default_model,
                {"reason": f"High density of sensitive entities ({sensitive_count})", "risk_level": "HIGH"}
            )

        # Default to cloud (which will receive the sanitized/masked prompt)
        return (
            "cloud",
            self.config.upstream.cloud_default_model,
            {"reason": "Masked prompt safe for cloud dispatch", "risk_level": "LOW"}
        )
