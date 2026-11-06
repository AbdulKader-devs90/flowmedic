"""Conservative signals in engineer-supplied Oracle session output."""

import re

from flowmedic.tracing import traced_tool


@traced_tool
def summarize(text: str) -> dict[str, bool]:
    """Detect positive lock observations, excluding explicit healthy negatives."""
    positive = re.search(
        r"enq:\s*TX|row lock contention|holds TX lock|"
        r"blocking_session\s*[=:]\s*[1-9]\d*|blocked:\s*[1-9]\d*",
        text,
        re.I,
    )
    return {"blocking_lock": bool(positive)}
