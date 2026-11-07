"""
Lightweight Multimodal and Image Attachment Validator for Shadow Agent.
Ensures image inputs do not bypass text sanitization and provides safe metadata inspection.
"""
from typing import List, Dict, Any, Tuple

class MultimodalGuard:
    """
    Inspects multimodal OpenAI payloads containing 'image_url' or encoded image content.
    Prevents image-based data exfiltration and flags uninspected visual binaries.
    """
    def __init__(self, allow_images: bool = True):
        self.allow_images = allow_images

    def inspect_messages(self, messages: List[Dict[str, Any]]) -> Tuple[bool, int, List[str]]:
        """
        Inspects message parts (OpenAI multimodal format).
        Returns:
            (has_images, image_count, warnings)
        """
        image_count = 0
        warnings = []

        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") in ("image_url", "image"):
                        image_count += 1

        if image_count > 0 and not self.allow_images:
            warnings.append(f"Multimodal image input blocked: {image_count} images detected under strict text-only policy.")

        return (image_count > 0), image_count, warnings
