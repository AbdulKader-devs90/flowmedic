"""Confirmed environment facts in LangGraph SQLite, with a small JSON fallback."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from flowmedic.config import REPO_ROOT, get_settings
from flowmedic.tracing import traced_tool

try:
    from langgraph.store.sqlite import SqliteStore
except ImportError:  # pragma: no cover - supported for minimal installations
    SqliteStore = None  # type: ignore[assignment, misc]


def local_path(path: Path) -> Path:
    """Reject symlink escapes before any runtime artifact write."""
    path = path if path.is_absolute() else REPO_ROOT / path
    if not path.resolve().is_relative_to(REPO_ROOT):
        raise ValueError("Runtime destination must remain inside the repository")
    return path


class EnvironmentMemory:
    def __init__(self, path: Path | None = None) -> None:
        suffix = ".sqlite" if SqliteStore is not None else ".json"
        self.path = local_path(
            path or get_settings().runs_dir / f"environments{suffix}"
        )
        self.sqlite = SqliteStore is not None and self.path.suffix != ".json"

    @traced_tool
    def read(self, environment: str) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        if self.sqlite:
            with SqliteStore.from_conn_string(str(self.path)) as store:
                store.setup()
                item = store.get(("environments",), environment)
                return item.value if item else {}
        return json.loads(self.path.read_text(encoding="utf-8")).get(environment, {})

    @traced_tool
    def latest_environment(self, platform: str) -> str | None:
        """Restore the most recently confirmed environment for this platform."""
        if not self.path.exists():
            return None
        if self.sqlite:
            with SqliteStore.from_conn_string(str(self.path)) as store:
                store.setup()
                items = store.search(
                    ("environments",), filter={"platform": platform}, limit=1000
                )
                data = {item.key: item.value for item in items}
        else:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        candidates = [
            (value.get("last_updated", ""), name)
            for name, value in data.items()
            if value.get("platform") == platform
        ]
        return max(candidates)[1] if candidates else None

    @traced_tool
    def confirm(self, environment: str, values: dict[str, Any]) -> None:
        confirmed = {
            **self.read(environment),
            **{
                k: v
                for k, v in values.items()
                if k in {"platform", "version", "os", "log_roots"} and v
            },
            "last_updated": datetime.now(UTC).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.sqlite:
            with SqliteStore.from_conn_string(str(self.path)) as store:
                store.setup()
                store.put(("environments",), environment, confirmed)
            return
        data = (
            json.loads(self.path.read_text(encoding="utf-8"))
            if self.path.exists()
            else {}
        )
        data[environment] = confirmed
        temporary = local_path(
            self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        )
        try:
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
