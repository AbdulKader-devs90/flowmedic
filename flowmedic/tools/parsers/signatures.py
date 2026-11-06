"""Deterministic error-signature extraction and code normalization."""

import re
from typing import Any

from pydantic import BaseModel

from flowmedic.tools.redact import redact
from flowmedic.tracing import traced_tool

CODE = re.compile(r"\b[A-Z]{2,}\.(?:\d+\.)*\d+[A-Z]?\b")
JAVA = r"\b(?:[a-zA-Z_$][\w$]*\.)*[A-Z][\w$]*(?:Exception|Error)\b"


class Signature(BaseModel):
    """Occurrence counts, timestamp bounds and one safe sample."""

    signature: str
    count: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    sample_line: str


def normalize_signature(value: str) -> str:
    """Strip numeric padding and severity suffixes only on product codes."""

    def code(match: re.Match[str]) -> str:
        groups = match[0].split(".")
        return (
            groups[0]
            + "."
            + ".".join(str(int(re.sub(r"[A-Z]$", "", group))) for group in groups[1:])
        )

    return CODE.sub(code, value.strip())


@traced_tool
def extract_signatures(
    text: str, profile: dict[str, Any] | None = None
) -> list[Signature]:
    """Match profile expressions plus Oracle codes and Java exceptions per line."""
    patterns = [r"\bORA-\d{5}\b", JAVA]
    for component in (profile or {}).get("components", []):
        patterns.extend(component.get("error_patterns", []))
    compiled = [re.compile(pattern) for pattern in patterns]
    found: dict[str, Signature] = {}
    for line in redact(text).text.splitlines():
        timestamp = re.search(
            r"\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?", line
        )
        seen = timestamp[0] if timestamp else None
        values = {
            normalize_signature(m[0])
            for regex in compiled
            for m in regex.finditer(line)
        }
        for value in sorted(values):
            if value not in found:
                found[value] = Signature(signature=value, sample_line=line)
            item = found[value]
            item.count += 1
            if seen:
                item.first_seen = min(item.first_seen or seen, seen)
                item.last_seen = max(item.last_seen or seen, seen)
    return list(found.values())
