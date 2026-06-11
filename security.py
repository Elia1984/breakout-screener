from __future__ import annotations

import re
from pathlib import Path


EXPECTED_EXTERNAL_HOSTS = (
    "api.nasdaq.com",
    "data.alpaca.markets",
    "feeds.finance.yahoo.com",
    "query1.finance.yahoo.com",
    "query2.finance.yahoo.com",
    "api.telegram.org",
)

SECRET_PATTERNS = {
    "telegram_bot_token": re.compile(r"\b\d{7,12}:[A-Za-z0-9_-]{30,}\b"),
    "openai_style_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "private_key": re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    "literal_secret_assignment": re.compile(
        r"(?i)\b(?:token|secret|api_key|apikey|chat_id|password)\b\s*=\s*['\"][^'\"]{8,}['\"]"
    ),
}


def audit_public_source(paths: list[str | Path]) -> list[str]:
    """Return warnings for obvious secret literals in public source files."""
    warnings: list[str] = []
    for item in paths:
        path = Path(item)
        if not path.exists() or path.name == "secrets.toml":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            warnings.append(f"{path}: cannot read: {exc}")
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if "secret_or_default(" in stripped or "read_secret(" in stripped:
                continue
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(stripped):
                    warnings.append(f"{path}:{line_number}: possible {label}")
    return warnings

