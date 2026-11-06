"""Counts from full JVM thread dumps or condensed field summaries."""

import re
from collections import Counter

from pydantic import BaseModel

from flowmedic.tracing import traced_tool


class ThreadSummary(BaseModel):
    """Counts represent threads, not occurrences of stack frames."""

    by_top_frame: dict[str, int]
    by_client_ip: dict[str, int]


@traced_tool
def summarize(text: str) -> ThreadSummary:
    """Count the first frame and client IP once per thread block."""
    frames: Counter[str] = Counter()
    clients: Counter[str] = Counter()
    if re.search(r'(?m)^"', text):
        blocks = re.split(r'(?m)(?=^"[^\n]+)', text)[1:]
        for block in blocks:
            frame = re.search(r"(?m)^\s*at\s+([^\s(]+)", block)
            frames[frame[1] if frame else "other"] += 1
            for ip in set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", block)):
                clients[ip] += 1
    else:
        for line in text.splitlines():
            count = re.match(r"\s*(\d+)\s+", line)
            if not count:
                continue
            n = int(count[1])
            frame = re.search(r"\bat\s+(\S+)", line)
            frames[frame[1] if frame else "other"] += n
            for ip in set(re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line)):
                clients[ip] += n
    return ThreadSummary(by_top_frame=dict(frames), by_client_ip=dict(clients))
