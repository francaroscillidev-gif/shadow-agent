"""
Self-contained SDK client for Shadow Agent.
Provides drop-in transparent usage without manual proxy URL wiring.
"""
from typing import Optional, List, Dict, Any, Generator
import httpx

class ShadowClient:
    """
    Client for interacting with local Shadow Agent proxy server.
    """
    def __init__(self, base_url: str = "http://127.0.0.1:8080/v1", api_key: str = "sk-shadow-local", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def chat(self, messages: List[Dict[str, str]], model: str = "shadow-auto", stream: bool = False) -> Dict[str, Any]:
        """
        Sends chat completion request through the local privacy proxy.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream
        }

        resp = self._client.post("/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> Dict[str, Any]:
        """Checks gateway and privacy vault health."""
        resp = self._client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def inspect_preview(self, text: str) -> Dict[str, Any]:
        """Inspects and returns sanitized preview and threat evaluation."""
        resp = self._client.post("/api/preview-mask", json={"text": text})
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
