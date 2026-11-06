"""Ordered adjacency checks over the reviewed topology, without model calls."""

from typing import Any

from flowmedic.knowledge.loaders import load_topology
from flowmedic.tracing import traced_tool


def _links(env: str, component_id: str) -> list[dict[str, Any]]:
    topology = load_topology(env)
    if component_id not in {c["id"] for c in topology["components"]}:
        raise ValueError(f"Unknown component {component_id!r} in {env!r}")
    return topology["links"]


@traced_tool
def dependencies(env: str, component_id: str) -> list[str]:
    """Immediate dependencies, hard first, preserving file order within each tier."""
    links = [link for link in _links(env, component_id) if link["from"] == component_id]
    return list(
        dict.fromkeys(
            link["to"]
            for link in sorted(links, key=lambda link: not link.get("hard", False))
        )
    )


@traced_tool
def callers(env: str, component_id: str) -> list[str]:
    """Immediate callers in reviewed file order."""
    return list(
        dict.fromkeys(
            link["from"]
            for link in _links(env, component_id)
            if link["to"] == component_id
        )
    )


@traced_tool
def related_checks(env: str, component_id: str) -> list[str]:
    """Check dependencies before affected callers, with no duplicate checks."""
    return list(
        dict.fromkeys(dependencies(env, component_id) + callers(env, component_id))
    )
