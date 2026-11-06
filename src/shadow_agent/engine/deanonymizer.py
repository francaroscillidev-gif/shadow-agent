"""Streaming and batch de-anonymizer for restoring sensitive values."""
from typing import Dict, AsyncGenerator
from shadow_agent.core.vault import EphemeralVault

class DeAnonymizer:
    """
    Restores masked placeholders / synthetic tokens back into real data.
    Provides batch restoration and streaming sliding-window reconstitution.
    """
    def __init__(self, vault: EphemeralVault):
        self.vault = vault

    def restore_batch(self, text: str) -> str:
        """Batch replacement of all mapped placeholders in text."""
        mappings = self.vault.get_all_mappings()
        if not mappings:
            return text

        restored = text
        for placeholder, original in mappings.items():
            if placeholder in restored:
                restored = restored.replace(placeholder, original)
        return restored

    async def restore_stream(self, stream_generator: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
        """
        Sliding-window stream processor.
        Handles tokens that get split across arbitrary SSE stream chunks.
        """
        mappings = self.vault.get_all_mappings()
        if not mappings:
            async for chunk in stream_generator:
                yield chunk
            return

        # Find maximum length of any placeholder to know buffer hold size
        max_placeholder_len = max(len(p) for p in mappings.keys())
        buffer = ""

        async for chunk in stream_generator:
            buffer += chunk

            # Try to replace any complete placeholders present in buffer
            for placeholder, original in mappings.items():
                if placeholder in buffer:
                    buffer = buffer.replace(placeholder, original)

            # Check if tail of buffer could be the start of an incomplete placeholder
            # If buffer is longer than max_placeholder_len, flush safe prefix
            if len(buffer) > max_placeholder_len:
                # Keep only potential partial match at the tail
                flush_length = len(buffer) - max_placeholder_len
                safe_chunk = buffer[:flush_length]
                buffer = buffer[flush_length:]
                yield safe_chunk

        # Flush remaining buffer at stream end after final replacement check
        if buffer:
            for placeholder, original in mappings.items():
                if placeholder in buffer:
                    buffer = buffer.replace(placeholder, original)
            yield buffer
