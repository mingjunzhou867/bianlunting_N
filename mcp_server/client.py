"""MCP Client — sync wrapper for async MCP stdio transport.

Spawns mcp_server/server.py as a subprocess, communicates via stdin/stdout.
Provides synchronous call_tool() interface for the synchronous ToolRegistry.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from loguru import logger


class MCPToolClient:
    """Synchronous MCP client that manages a server subprocess."""

    def __init__(self, server_script: str | None = None):
        self._server_script = server_script or os.path.join(
            os.path.dirname(__file__), "server.py",
        )
        self._session: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._available = False
        self._tools: list[dict[str, Any]] = []
        self._start()

    def _start(self) -> None:
        """Start the MCP server subprocess and connect."""
        try:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_loop, daemon=True, name="mcp-client-loop",
            )
            self._thread.start()

            # Connect to server (blocks until ready)
            future = self._submit(self._connect_async())
            future.result(timeout=15)
            self._available = True
            logger.info("[MCP Client] 已连接到 MCP Server，可用工具: {}", [t["name"] for t in self._tools])
        except Exception as exc:
            logger.warning("[MCP Client] MCP Server 启动失败，回退到直接调用: {}", exc)
            self._available = False

    def _run_loop(self) -> None:
        """Run the async event loop in a background thread."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coro) -> Future:
        """Submit a coroutine to the background event loop."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def _connect_async(self) -> None:
        """Connect to the MCP server via stdio."""
        from mcp import ClientSession, StdioServerParameters, stdio_client

        # Ensure project root is in PYTHONPATH for the subprocess
        project_root = str(Path(__file__).parent.parent)
        env = os.environ.copy()
        existing_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = project_root + (os.pathsep + existing_path if existing_path else "")

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self._server_script],
            env=env,
        )

        # Start server process and get transport
        self._transport = stdio_client(server_params)
        read_stream, write_stream = await self._transport.__aenter__()

        # Create session
        self._session_ctx = ClientSession(read_stream, write_stream)
        self._session = await self._session_ctx.__aenter__()

        # Initialize
        await self._session.initialize()

        # List available tools
        tools_result = await self._session.list_tools()
        self._tools = [
            {"name": t.name, "description": t.description or "", "parameters": t.inputSchema}
            for t in tools_result.tools
        ]

    @property
    def available(self) -> bool:
        return self._available

    @property
    def tools(self) -> list[dict[str, Any]]:
        return self._tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the MCP server synchronously.

        Returns the tool result as a string, or raises on failure.
        """
        if not self._available or not self._session:
            raise RuntimeError("MCP Client not available")

        future = self._submit(self._call_tool_async(name, arguments))
        return future.result(timeout=30)

    async def _call_tool_async(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the MCP server asynchronously."""
        result = await self._session.call_tool(name, arguments)
        # Extract text content from result
        parts = []
        for item in result.content:
            if hasattr(item, "text"):
                parts.append(item.text)
            else:
                parts.append(str(item))
        return "\n".join(parts)

    def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the MCP server."""
        return self._tools

    def close(self) -> None:
        """Shut down the MCP client and server subprocess."""
        if self._session and self._loop:
            try:
                future = self._submit(self._close_async())
                future.result(timeout=5)
            except Exception:
                pass
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=3)
        self._available = False
        logger.info("[MCP Client] 已关闭")

    async def _close_async(self) -> None:
        """Close the MCP session and transport."""
        try:
            if self._session:
                await self._session_ctx.__aexit__(None, None, None)
            if hasattr(self, "_transport"):
                await self._transport.__aexit__(None, None, None)
        except Exception:
            pass
