"""
Fast sub-millisecond heuristic detector for Prompt Injection, Jailbreaks, and System Prompt Leaking.
"""
import re
from typing import Tuple, List, Dict

class InjectionGuard:
    """
    Evaluates incoming prompts for prompt injection, adversarial delimiters,
    and jailbreak patterns.
    """
    
    INJECTION_PATTERNS = [
        # Instruction Overrides
        (re.compile(r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|prompts|rules)\b"), "INSTRUCTION_OVERRIDE", 0.95),
        (re.compile(r"(?i)\bdisregard\s+(the\s+)?(previous|initial)\s+(instructions|system\s+prompt)\b"), "INSTRUCTION_OVERRIDE", 0.95),
        (re.compile(r"(?i)\byou\s+are\s+now\s+(an\s+unfiltered|DAN|in\s+developer\s+mode|unconstrained)\b"), "JAILBREAK_ROLEPLAY", 0.90),
        
        # System Prompt Extraction / Leaking
        (re.compile(r"(?i)\b(repeat|output|show|print|reveal)\s+(the\s+)?(entire\s+)?(system\s+prompt|initial\s+instructions)\b"), "SYSTEM_PROMPT_LEAK", 0.90),
        
        # Adversarial Delimiters & Tag Smuggling
        (re.compile(r"(?i)<\/?(?:system|developer|assistant|admin)>"), "DELIMITER_SMUGGLING", 0.85),
        (re.compile(r"(?i)\[(?:SYSTEM|INSTRUCTION|ADMIN)\]"), "DELIMITER_SMUGGLING", 0.85),
        
        # Roleplay / Jailbreak Triggers
        (re.compile(r"(?i)\bdo\s+anything\s+now\b"), "JAILBREAK_ROLEPLAY", 0.95),
        (re.compile(r"(?i)\bbypass\s+(all\s+)?(safety|moderation|filters)\b"), "SAFETY_BYPASS_ATTEMPT", 0.95),
    ]

    def scan(self, text: str) -> Tuple[bool, float, List[Dict[str, str]]]:
        """
        Scans text for injection risks.
        Returns:
            (is_threat, highest_risk_score, matched_threats)
        """
        if not text:
            return False, 0.0, []

        matches = []
        max_score = 0.0

        for pattern, category, score in self.INJECTION_PATTERNS:
            if pattern.search(text):
                matches.append({
                    "category": category,
                    "threat_score": score
                })
                if score > max_score:
                    max_score = score

        is_threat = max_score >= 0.85
        return is_threat, max_score, matches
