"""Read uptime, free and vmstat output; preserve the source memory units."""

import re

from pydantic import BaseModel, Field

from flowmedic.tracing import traced_tool


class HostSummary(BaseModel):
    """Latest vmstat sample; swap units follow the input free command."""

    load: list[float] = Field(default_factory=list)
    swap_used: int | None = None
    si: int | None = None
    so: int | None = None


@traced_tool
def summarize(text: str) -> HostSummary:
    """Handle standard tables and compact scenario summary lines."""
    result = HostSummary()
    load = re.search(r"load averages?:\s*([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)", text)
    if load:
        result.load = [float(v) for v in load.groups()]
    swap = re.search(r"Swap:\s*\d+\s+(\d+)|Swap total \d+, used (\d+)", text)
    if swap:
        result.swap_used = int(next(v for v in swap.groups() if v is not None))
    compact = re.search(r"\bsi\s+(\d+)\s+so\s+(\d+)", text)
    if compact:
        result.si, result.so = map(int, compact.groups())
    headers: list[str] = []
    for line in text.splitlines():
        columns = line.split()
        if "si" in columns and "so" in columns and "swpd" in columns:
            headers = columns
        elif (
            headers
            and len(columns) == len(headers)
            and all(c.isdigit() for c in columns)
        ):
            result.si = int(columns[headers.index("si")])
            result.so = int(columns[headers.index("so")])
    return result
