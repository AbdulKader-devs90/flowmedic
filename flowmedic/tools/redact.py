"""Mask secrets and quarantine instruction-like diagnostic lines."""

import re

from pydantic import BaseModel

from flowmedic.tracing import traced_tool


class RedactedText(BaseModel):
    """Safe text and separately flagged, also masked, suspicious lines."""

    text: str
    suspicious_lines: list[str]


@traced_tool
def redact(text: str) -> RedactedText:
    """Remove credentials before any text reaches a model or trace."""
    text = re.sub(
        r"-----BEGIN ([A-Z ]*PRIVATE KEY)-----.*?(?:-----END \1-----|\Z)",
        "[REDACTED PRIVATE KEY]",
        text,
        flags=re.S,
    )
    text = re.sub(
        r"(?i)(Authorization\s*:\s*(?:Basic|Bearer)\s+)\S+", r"\1[REDACTED]", text
    )
    text = re.sub(
        r"""(?ix)(["']?(?:password|passwd|pwd|[\w-]*token|api[_-]?key|secret)
        ["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;]+)""",
        r"\1[REDACTED]",
        text,
    )
    suspicious: list[str] = []
    safe: list[str] = []
    for line in text.splitlines():
        if re.search(
            r"(?i)ignore\b.*\b(?:previous|prior|all)\b.*\binstructions|"
            r"note\s+to\s+(?:ai|assistant)|system\s+prompt",
            line,
        ):
            suspicious.append(line)
            safe.append("[SUSPICIOUS LINE REMOVED]")
        else:
            safe.append(line)
    return RedactedText(text="\n".join(safe), suspicious_lines=suspicious)
