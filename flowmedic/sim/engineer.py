"""Most specific unused fixture entry wins; every keyword must match."""

import json
from pathlib import Path
from typing import Any

import yaml

from flowmedic.graph.state import StepReply
from flowmedic.tracing import traced_tool


class EngineerSimulator:
    def __init__(self, path: Path) -> None:
        self.data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.used: set[int] = set()

    @traced_tool
    def answer(self, step: dict[str, Any]) -> dict[str, Any]:
        text = " ".join(
            str(step.get(k, "")) for k in ("title", "command_or_action")
        ).casefold()
        candidates = [
            (len(entry["match"]), index, entry)
            for index, entry in enumerate(self.data.get("steps", []))
            if index not in self.used
            and all(str(keyword).casefold() in text for keyword in entry["match"])
        ]
        if candidates:
            # Most keywords wins; negative index preserves fixture order on ties.
            _, index, entry = max(candidates, key=lambda item: (item[0], -item[1]))
            self.used.add(index)
        else:
            entry = self.data["default"]
        return StepReply(
            status=entry["status"],
            output=entry["output"],
            confirmed=step.get("kind") in {"change", "destructive"},
        ).model_dump()

    def __repr__(self) -> str:
        return json.dumps({"entries": len(self.data.get("steps", []))})
