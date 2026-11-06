"""Count TCP connections by peer endpoint from ss output or count summaries."""

import re
from collections import Counter

from flowmedic.tracing import traced_tool


@traced_tool
def summarize(text: str) -> dict[str, int]:
    """Aggregate peers; repeated per-node summary counts are summed."""
    counts: Counter[str] = Counter()
    target: str | None = None
    for line in text.splitlines():
        if "grep" in line:
            match = re.search(r"((?:\d{1,3}\\?\.){3}\d{1,3}).*?:(\d+)", line)
            if match:
                target = f"{match[1].replace(chr(92), '')}:{match[2]}"
        elif target and line.strip().isdigit():
            counts[target] += int(line.strip())
            target = None
        else:
            columns = line.split()
            offset = 1 if columns and columns[0] in {"tcp", "tcp6"} else 0
            if len(columns) >= offset + 5 and columns[offset] in {
                "ESTAB",
                "SYN-SENT",
                "CLOSE-WAIT",
                "TIME-WAIT",
                "FIN-WAIT-1",
                "FIN-WAIT-2",
            }:
                counts[columns[offset + 4]] += 1
    return dict(counts)
