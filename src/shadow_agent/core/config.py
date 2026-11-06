"""Shadow Agent Configuration."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import os
import yaml

class UpstreamConfig(BaseModel):
    cloud_url: str = Field(default="https://api.openai.com/v1")
    cloud_api_key: Optional[str] = Field(default=None)
    cloud_default_model: str = Field(default="gpt-4o-mini")
    
    local_url: str = Field(default="http://localhost:11434/v1")
    local_api_key: str = Field(default="ollama")
    local_default_model: str = Field(default="qwen2.5-coder:7b")

class PrivacyPolicy(BaseModel):
    mask_api_keys: bool = True
    mask_emails: bool = True
    mask_ip_addresses: bool = True
    mask_credit_cards: bool = True
    mask_jwt_tokens: bool = True
    mask_ibans: bool = True
    synthetic_replacement: bool = True  # Use realistic synthetic values instead of [TOKEN]
    custom_patterns: Dict[str, str] = Field(default_factory=dict)
    enable_cache: bool = True  # Local semantic cache
    
    # Auto routing rules
    auto_route_to_local_if_unmaskable: bool = True
    force_local_keywords: List[str] = Field(default_factory=lambda: [
        "top-secret", "proprietary algorithm", "confidential internal", "patient record"
    ])

class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    upstream: UpstreamConfig = Field(default_factory=UpstreamConfig)
    privacy: PrivacyPolicy = Field(default_factory=PrivacyPolicy)
    audit_log_path: str = "shadow_audit.jsonl"

def load_config(config_path: Optional[str] = None) -> ServerConfig:
    config = ServerConfig()
    
    # Load from file if exists
    path = config_path or "shadow_agent.yaml"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            config = ServerConfig.model_validate(data)
            
    # Environment overrides
    if env_key := os.getenv("UPSTREAM_API_KEY") or os.getenv("OPENAI_API_KEY"):
        config.upstream.cloud_api_key = env_key
    if env_cloud_url := os.getenv("UPSTREAM_BASE_URL"):
        config.upstream.cloud_url = env_cloud_url
    if env_local_url := os.getenv("LOCAL_LLM_URL"):
        config.upstream.local_url = env_local_url

    return config
