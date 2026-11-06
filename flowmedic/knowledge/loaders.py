"""Read repository content independently of the working directory."""

import json
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from flowmedic.config import REPO_ROOT
from flowmedic.graph.state import Category, Severity


class KnowledgeDoc(BaseModel):
    """Front matter plus original Markdown body."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    doc_id: str = Field(alias="id")
    doc_type: Literal["incident", "runbook"] = Field(alias="type")
    title: str
    platform: str
    category: Category
    secondary_categories: list[Category] = Field(default_factory=list)
    severity: Severity | None = None
    versions: list[str] = Field(default_factory=list)
    os: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    signatures: list[str] = Field(default_factory=list)
    root_causes: list[str] = Field(default_factory=list)
    runbooks: list[str] = Field(default_factory=list)
    source: str | None = None
    verified: bool = False
    body: str

    def embedding_text(self) -> str:
        """Use diagnosis sections, excluding resolution instructions."""
        parts = [self.title, " ".join(self.signatures)]
        sections = re.split(r"(?m)^## ", self.body)
        for section in sections[1:]:
            if section.startswith(("Symptoms", "Root cause")):
                parts.append(section)
        signal = re.search(r"\*\*Signals:\*\*(.*?)(?:\n\n|$)", self.body, re.S)
        if signal:
            parts.append(signal[1])
        causes = load_root_causes()
        parts.extend(causes[cause]["description"] for cause in self.root_causes)
        return "\n".join(parts)


class Scenario(BaseModel):
    """Raw local fixture; redact before use by an embedding or language model."""

    case_id: str
    problem: str
    logs: dict[str, str]
    expected: dict[str, Any]


def _path(parent: Path, name: str, suffix: str = "") -> Path:
    if not re.fullmatch(r"[\w-]+", name):
        raise ValueError(f"Invalid content identifier: {name!r}")
    path = parent / f"{name}{suffix}"
    if not path.resolve().is_relative_to(parent.resolve()):
        raise ValueError(f"Content path escapes repository: {name!r}")
    return path


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_categories() -> dict[str, str]:
    """Return the fixed category vocabulary."""
    return _yaml(REPO_ROOT / "knowledge/categories.yaml")["categories"]


def load_root_causes() -> dict[str, dict[str, str]]:
    """Return controlled root-cause descriptions and validate categories."""
    causes = _yaml(REPO_ROOT / "knowledge/root_causes.yaml")["root_causes"]
    for key, cause in causes.items():
        if cause["category"] not in load_categories():
            raise ValueError(f"root_causes.yaml: {key}: unknown category")
    return causes


def load_profile(platform_id: str) -> dict[str, Any]:
    """Load one platform profile."""
    return _yaml(_path(REPO_ROOT / "platforms", platform_id, ".yaml"))


def load_topology(environment: str) -> dict[str, Any]:
    """Load one reviewed component map."""
    return _yaml(_path(REPO_ROOT / "environments", environment) / "topology.yaml")


def load_documents() -> list[KnowledgeDoc]:
    """Validate all front matter, vocabulary references and unique document IDs."""
    causes = load_root_causes()
    docs: list[KnowledgeDoc] = []
    ids: set[str] = set()
    for folder in ("incidents", "runbooks"):
        for path in sorted((REPO_ROOT / "knowledge" / folder).glob("*.md")):
            try:
                match = re.fullmatch(
                    r"---\r?\n(.*?)\r?\n---\r?\n(.*)",
                    path.read_text(encoding="utf-8"),
                    re.S,
                )
                if not match:
                    raise ValueError("missing YAML front matter")
                doc = KnowledgeDoc(**yaml.safe_load(match[1]), body=match[2])
                unknown = set(doc.root_causes) - causes.keys()
                if unknown:
                    raise ValueError(f"unknown root_causes IDs: {sorted(unknown)}")
                if doc.doc_id in ids:
                    raise ValueError(f"duplicate document ID: {doc.doc_id}")
                ids.add(doc.doc_id)
                docs.append(doc)
            except (ValueError, ValidationError, yaml.YAMLError) as exc:
                raise ValueError(f"{path.relative_to(REPO_ROOT)}: {exc}") from exc
    return docs


def list_scenarios() -> list[str]:
    """List fixture identifiers in deterministic order."""
    return sorted(
        p.parent.name for p in (REPO_ROOT / "data/scenarios").glob("*/problem.md")
    )


def load_scenario(
    case_id: str,
    *,
    include_logs: bool = True,
    include_expected: bool = True,
) -> Scenario:
    """Read a local fixture; triage defers logs until approval and excludes labels."""
    path = _path(REPO_ROOT / "data/scenarios", case_id)
    problem = (path / "problem.md").resolve(strict=True)
    if not problem.is_relative_to(path.resolve()):
        raise ValueError("Scenario problem escapes its folder")
    return Scenario(
        case_id=case_id,
        problem=problem.read_text("utf-8"),
        logs={
            str(p.relative_to(path / "logs")): p.read_text("utf-8")
            for p in sorted((path / "logs").rglob("*"))
            if p.is_file()
        }
        if include_logs
        else {},
        expected=json.loads((path / "expected.json").read_text("utf-8"))
        if include_expected
        else {},
    )
