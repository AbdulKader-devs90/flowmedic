"""Thin adapter: fixed local stdio service, with startup-only local fallback."""

import asyncio
import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from flowmedic.config import REPO_ROOT, get_settings
from mcp_servers.log_reader.server import LogReader


class LogClient:
    """The caller supplies approved roots; no model can choose the subprocess."""

    def __init__(self, roots: list[Path], *, mode: str | None = None) -> None:
        scenario_base = REPO_ROOT / "data/scenarios"
        allowed = [
            p.resolve()
            for p in scenario_base.glob("*/logs")
            if p.resolve().is_relative_to(scenario_base)
        ] + [
            (p if p.is_absolute() else REPO_ROOT / p).resolve()
            for p in get_settings().log_roots
        ]
        resolved = [(p if p.is_absolute() else REPO_ROOT / p).resolve() for p in roots]
        if any(not any(p.is_relative_to(root) for root in allowed) for p in resolved):
            raise ValueError(
                "Only scenario logs or configured LOG_ROOTS may be approved"
            )
        self.reader = LogReader(resolved)
        self.mode = mode or get_settings().log_transport
        self.fallback_reason: str | None = None
        self.tools: dict[str, Any] = {}
        self.stack = AsyncExitStack()

    async def __aenter__(self) -> "LogClient":
        if self.mode == "inprocess":
            return self
        self.client = MultiServerMCPClient(
            {
                "logs": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": ["-m", "mcp_servers.log_reader.server"],
                    "cwd": str(REPO_ROOT),
                    "env": {
                        "LOG_ROOTS": json.dumps([str(p) for p in self.reader.roots]),
                        "LANGSMITH_TRACING": "false",
                    },
                }
            }
        )
        try:
            async with asyncio.timeout(20):
                session = await self.stack.enter_async_context(
                    self.client.session("logs")
                )
                self.tools = {t.name: t for t in await load_mcp_tools(session)}
            if set(self.tools) != {"list_files", "grep", "tail", "stats"}:
                raise RuntimeError("Unexpected MCP tool set")
        except Exception as exc:
            await self.stack.aclose()
            self.mode = "inprocess"
            self.fallback_reason = (
                f"MCP startup failed ({type(exc).__name__}); using local reader."
            )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Always close the local MCP session and subprocess."""
        await self.stack.aclose()

    async def call(
        self, name: str, *, config: RunnableConfig | None = None, **arguments: Any
    ) -> dict[str, Any]:
        """Invoke identical tool contracts; a tool rejection never triggers fallback."""
        if name not in {"list_files", "grep", "tail", "stats"}:
            raise ValueError("Unknown read-only tool")
        if self.mode == "inprocess":
            return getattr(self.reader, name)(**arguments)
        result = await asyncio.wait_for(
            self.tools[name].ainvoke(arguments, config=config), timeout=30
        )
        if isinstance(result, dict):
            return result
        # Adapters preserve structured output as JSON text content blocks.
        if isinstance(result, list):
            result = next(
                block["text"] for block in result if block.get("type") == "text"
            )
        return json.loads(result)

    async def list_files(self, root: str, **kwargs: Any) -> dict[str, Any]:
        return await self.call("list_files", root=root, **kwargs)

    async def grep(self, path: str, pattern: str, **kwargs: Any) -> dict[str, Any]:
        return await self.call("grep", path=path, pattern=pattern, **kwargs)

    async def tail(self, path: str, lines: int = 200, **kwargs: Any) -> dict[str, Any]:
        return await self.call("tail", path=path, lines=lines, **kwargs)

    async def stats(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return await self.call("stats", path=path, **kwargs)
