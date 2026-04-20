import asyncio

from agents.mcp import MCPServerStdio

# ---------------------------------------------------------------------------
# MCP server singleton — spawned once per process, reused across all messages.
# Avoids the cost of launching a new `npx` subprocess on every invocation.
# ---------------------------------------------------------------------------
_mcp_server: MCPServerStdio | None = None
_mcp_lock: asyncio.Lock | None = None


async def _get_mcp_file_server() -> MCPServerStdio:
    """Return the process-level MCP server, creating it on first call."""
    global _mcp_server, _mcp_lock
    if _mcp_lock is None:
        _mcp_lock = asyncio.Lock()
    async with _mcp_lock:
        if _mcp_server is None:
            server = MCPServerStdio(
                params={
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
                },
                client_session_timeout_seconds=30,
            )
            await server.__aenter__()
            _mcp_server = server
    return _mcp_server
