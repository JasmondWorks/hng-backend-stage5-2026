import re

_INJECTION_PATTERNS: list[str] = [
    r"ignore\s+previous\s+instructions",
    r"###\s*SYSTEM",
    r"<\|endoftext\|>",
    r"system\s+role\s*:",
    r"you\s+are\s+now",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


def sanitise(text: str) -> str:
    for pattern in _COMPILED:
        text = pattern.sub("", text)
    return text
