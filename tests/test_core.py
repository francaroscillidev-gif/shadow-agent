"""Tests for Masking, Streaming De-anonymization, and Ephemeral Vault."""
import pytest
import asyncio
from shadow_agent.core.vault import EphemeralVault
from shadow_agent.engine.masker import MaskingEngine
from shadow_agent.engine.deanonymizer import DeAnonymizer
from shadow_agent.router.policy_router import Router
from shadow_agent.core.config import ServerConfig

def test_masking_and_deanonymization():
    vault = EphemeralVault()
    masker = MaskingEngine(use_synthetic=True)
    deanonymizer = DeAnonymizer(vault)

    text = "Contatta dev@company.com con API key sk-proj-1234567890abcdef1234567890abcdef."
    masked, entities = masker.mask(text, vault)

    # Must detect both email and key
    assert len(entities) == 2
    assert "dev@company.com" not in masked
    assert "sk-proj-1234567890abcdef" not in masked
    assert "example-sandbox.org" in masked

    # Restoration must bring original text back exactly
    restored = deanonymizer.restore_batch(masked)
    assert restored == text

@pytest.mark.asyncio
async def test_streaming_reconstitution_split_tokens():
    vault = EphemeralVault()
    masker = MaskingEngine(use_synthetic=True)
    deanonymizer = DeAnonymizer(vault)

    secret = "sk-proj-1234567890abcdef1234567890abcdef"
    text = f"La tua chiave e {secret}"
    masked, _ = masker.mask(text, vault)

    # Get synthetic placeholder used
    synthetic_key = list(vault.get_all_mappings().keys())[0]

    # Simulate chunks where synthetic_key is cut in half across two stream SSE chunks
    part1 = synthetic_key[:8]
    part2 = synthetic_key[8:]

    async def mock_stream():
        yield "La tua "
        yield f"chiave e {part1}"
        yield part2
        yield " ok?"

    accumulated = ""
    async for restored_chunk in deanonymizer.restore_stream(mock_stream()):
        accumulated += restored_chunk

    assert accumulated == f"La tua chiave e {secret} ok?"

def test_airgap_routing():
    config = ServerConfig()
    router = Router(config)

    # Query with normal data
    dest, model, meta = router.inspect_and_route([{"content": "How do I reverse a string?"}], sensitive_count=0)
    assert dest == "cloud"

    # Query with airgap keyword
    dest_airgap, model_airgap, meta_airgap = router.inspect_and_route(
        [{"content": "Review this proprietary algorithm for security"}],
        sensitive_count=0
    )
    assert dest_airgap == "local"
    assert meta_airgap["risk_level"] == "CRITICAL"
