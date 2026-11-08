"""Read-only FastMCP tools; no diagnostic content is written or executed."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from flowmedic.config import REPO_ROOT, get_settings
from flowmedic.tools.redact import redact
from flowmedic.tracing import traced_tool

MAX_BYTES = 50 * 1024 * 1024
TIMESTAMP = re.compile(r"\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?")


def timestamp(line: str) -> str | None:
    """Normalize the supported diagnostic timestamp for comparisons."""
    match = TIMESTAMP.search(line)
    return (
        match[0].replace("/", "-").replace("T", " ").replace(",", ".")
        if match
        else None
    )


def time_bound(value: str | None) -> str | None:
    """Reject ambiguous or invalid time windows."""
    if value is None:
        return None
    normalized = timestamp(value)
    if normalized is None:
        raise ValueError("Time window must use YYYY-MM-DD HH:MM:SS")
    datetime.fromisoformat(normalized)
    return normalized


class LogReader:
    """One implementation shared by the stdio service and in-process client."""

    def __init__(self, roots: list[Path]) -> None:
        self.roots = [
            (p if p.is_absolute() else REPO_ROOT / p).resolve(strict=True)
            for p in roots
        ]
        if any(not p.is_dir() for p in self.roots):
            raise ValueError("Log roots must be directories")

    def _path(self, value: str, *, directory: bool = False) -> Path:
        path = Path(value)
        if ".." in path.parts or ".." in value.replace("\\", "/").split("/"):
            raise ValueError("Path traversal is forbidden")
        if not path.is_absolute():
            path = REPO_ROOT / path
        resolved = path.resolve(strict=True)
        if not any(resolved.is_relative_to(root) for root in self.roots):
            raise ValueError("Path is outside approved log roots")
        if directory:
            if not resolved.is_dir():
                raise ValueError("Expected a directory")
        elif not resolved.is_file() or resolved.stat().st_size > MAX_BYTES:
            raise ValueError("Expected a regular file no larger than 50 MB")
        return resolved

    @traced_tool
    def list_files(self, root: str) -> dict[str, Any]:
        """List only readable files; reject escaping links and oversized files."""
        folder = self._path(root, directory=True)
        files = []
        for candidate in sorted(folder.rglob("*")):
            if any(
                part.startswith(".") for part in candidate.relative_to(folder).parts
            ):
                continue
            if candidate.is_symlink() or candidate.is_file():
                path = self._path(str(candidate))
                info = path.stat()
                if info.st_size == 0:
                    continue
                files.append(
                    {
                        "name": str(candidate.relative_to(folder)),
                        "path": str(candidate),
                        "size": info.st_size,
                        "modified_time": info.st_mtime,
                    }
                )
        return {"files": files}

    def _read(self, path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        checked = self._path(path)
        # Bounded read also catches a file growing after stat(). Read-only mode.
        with checked.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("File exceeds 50 MB")
        flags = []
        # Redact individual lines to preserve references to the original line numbers.
        lines = []
        private = False
        for n, raw in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
            if "-----BEGIN " in raw and "PRIVATE KEY-----" in raw:
                private = True
            if private:
                text = "[REDACTED PRIVATE KEY]"
                if "-----END " in raw and "PRIVATE KEY-----" in raw:
                    private = False
            else:
                item = redact(raw)
                if item.suspicious_lines:
                    flags.append(
                        {"file": path, "line_no": n, "text": item.suspicious_lines[0]}
                    )
                    continue
                text = item.text
            lines.append({"line_no": n, "text": text})
        return lines, flags

    @traced_tool
    def grep(
        self,
        path: str,
        pattern: str,
        start_time: str | None = None,
        end_time: str | None = None,
        max_lines: int = 200,
    ) -> dict[str, Any]:
        """Match safe lines within the requested inclusive window."""
        if not 1 <= max_lines <= 10000:
            raise ValueError("max_lines must be between 1 and 10000")
        start, end = time_bound(start_time), time_bound(end_time)
        if start and end and start > end:
            raise ValueError("Time window is reversed")
        regex = re.compile(pattern)
        lines, flags = self._read(path)
        selected = []
        current: str | None = None
        selected_flags = []
        combined = [(line, False) for line in lines] + [(flag, True) for flag in flags]
        for line, flagged in sorted(combined, key=lambda item: item[0]["line_no"]):
            current = timestamp(line["text"]) or current
            if (start or end) and current is None:
                continue
            if start and current and current < start:
                continue
            if end and current and current > end:
                continue
            if flagged:
                selected_flags.append(line)
            elif regex.search(line["text"]):
                selected.append(line)
        return {
            "lines": selected[:max_lines],
            "flagged": selected_flags,
            "truncated": len(selected) > max_lines,
        }

    @traced_tool
    def tail(self, path: str, lines: int = 200) -> dict[str, Any]:
        """Return the last safe lines with original references."""
        if not 1 <= lines <= 10000:
            raise ValueError("lines must be between 1 and 10000")
        safe, flags = self._read(path)
        return {
            "lines": safe[-lines:],
            "flagged": flags,
            "truncated": len(safe) > lines,
        }

    @traced_tool
    def stats(self, path: str) -> dict[str, Any]:
        """Report safe-line counts and timestamp bounds, without raw content."""
        safe, flags = self._read(path)
        times = [t for line in safe + flags if (t := timestamp(line["text"]))]
        return {
            "line_count": max((line["line_no"] for line in safe + flags), default=0),
            "first_timestamp": min(times, default=None),
            "last_timestamp": max(times, default=None),
            "flagged": flags,
        }


def create_server(roots: list[Path]) -> FastMCP:
    """Expose exactly four read-only tools."""
    reader = LogReader(roots)
    server = FastMCP("flowmedic-log-reader", log_level="WARNING")
    for method in (reader.list_files, reader.grep, reader.tail, reader.stats):
        server.tool()(method)
    return server


if __name__ == "__main__":
    create_server(get_settings().log_roots).run(transport="stdio")
