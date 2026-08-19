import re

# Block common prompt injection phrases
JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"system\s*prompt",
    r"act\s+as\s+an\s+unrestricted",
    r"forget\s+(your\s+)?rules"
]

# Sensitive PII patterns (Credit Card numbers, CVVs, Passwords)
CREDIT_CARD_PATTERN = r"\b(?:\d[ -]*?){13,16}\b"
CVV_PASSWORD_PATTERN = r"\b(cvv|cvc|password|pin)\s*[:=]?\s*\w+\b"


def run_input_guardrails(query: str) -> tuple[bool, str]:
    """
    Validates inbound query for safety and enterprise compliance.
    Returns: (is_safe: bool, rejection_message: str)
    """
    # 1. Prompt Injection Check
    for pattern in JAILBREAK_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            return False, "Security Alert: Query flagged for policy violation (Prompt Injection detected)."

    # 2. Sensitive Financial/Security PII Check
    if re.search(CREDIT_CARD_PATTERN, query) or re.search(CVV_PASSWORD_PATTERN, query, re.IGNORECASE):
        return False, "Security Notice: For your safety, please do not share credit card numbers, CVVs, or passwords via email."

    return True, ""