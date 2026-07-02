"""Google Docs MCP session — wraps the proven mcp-test/create_doc.py stdio pattern.

The proxy holds the live MCP stdio session and OAuth credentials.
The specialist runtime never touches this; it only presents a grant_token.

M1.5: establishes the session; exposes call_tool(name, args).
M12:  this in-process holder becomes the out-of-process Scoped MCP Proxy (:8003).

One-time OAuth: on first call, the MCP server will emit a Google OAuth URL.
call_with_auth_retry() detects it, opens the browser, waits for Enter, then retries.
"""
from __future__ import annotations

import asyncio
import os
import re
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import (
    GDOCS_MCP_CWD,
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    MCP_SINGLE_USER_MODE,
    USER_GOOGLE_EMAIL,
    WORKSPACE_MCP_ENABLED_TOOLS,
)

_AUTH_URL_RE = re.compile(r"https://accounts\.google\.com/o/oauth2/auth\S+")


def _extract_auth_url(text: str) -> str | None:
    m = _AUTH_URL_RE.search(text)
    return m.group(0) if m else None


def _server_params() -> StdioServerParameters:
    env = {
        "GOOGLE_OAUTH_CLIENT_ID": GOOGLE_OAUTH_CLIENT_ID,
        "GOOGLE_OAUTH_CLIENT_SECRET": GOOGLE_OAUTH_CLIENT_SECRET,
        "WORKSPACE_MCP_ENABLED_TOOLS": WORKSPACE_MCP_ENABLED_TOOLS,
        "MCP_SINGLE_USER_MODE": MCP_SINGLE_USER_MODE,
        "USER_GOOGLE_EMAIL": USER_GOOGLE_EMAIL,
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
    }
    # On Windows, os.path.expanduser("~") inside the subprocess needs USERPROFILE
    # (and other Windows env vars) to find the OAuth credential cache.
    # Without them the credential store falls back to a cwd-relative path that
    # has no token, causing the MCP call to fail silently.
    for win_var in ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "SystemRoot", "HOMEDRIVE", "HOMEPATH"):
        val = os.environ.get(win_var)
        if val:
            env[win_var] = val
    return StdioServerParameters(
        command="uv",
        args=["run", "workspace-mcp", "--transport", "stdio"],
        cwd=GDOCS_MCP_CWD,
        env=env,
    )


class GDocsSession:
    """Long-lived gdocs MCP session.  Initialise once; reuse across tasks.

    Usage:
        session = GDocsSession()
        await session.start()
        result = await session.call_tool("create_doc", {"title": "..."})
        await session.stop()

    Or use as an async context manager.
    """

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._cm = None
        self._started = False

    async def start(self) -> None:
        params = _server_params()
        self._cm = stdio_client(params)
        read, write = await self._cm.__aenter__()
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()
        self._session = session
        self._started = True

    async def stop(self) -> None:
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None
        if self._cm:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:
                pass
            self._cm = None
        self._started = False

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool, handling the one-time OAuth browser flow."""
        if not self._started or self._session is None:
            raise RuntimeError("GDocsSession not started — call await session.start() first")
        return await _call_with_auth_retry(self._session, tool_name, arguments)

    async def __aenter__(self) -> "GDocsSession":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()


async def _call_with_auth_retry(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Call a tool; if the MCP server returns an OAuth URL, prompt for consent then retry."""
    while True:
        result = await session.call_tool(tool_name, arguments=arguments)
        text = "".join(getattr(block, "text", "") for block in result.content)
        auth_url = _extract_auth_url(text)
        if auth_url:
            print(f"\n*** GOOGLE OAUTH REQUIRED ***")
            print(f"\nOpen this URL in your browser:\n\n{auth_url}\n")
            # In server context we can't use input(). Log and wait 30s for the user to authenticate.
            print("Waiting 30 s for browser consent… (press Ctrl+C to abort)")
            await asyncio.sleep(30)
        else:
            return result


# ── Module-level singleton (in-process proxy, M6) ─────────────────────────────
_gdocs_session: GDocsSession | None = None


def get_gdocs_session() -> GDocsSession:
    global _gdocs_session
    if _gdocs_session is None:
        _gdocs_session = GDocsSession()
    return _gdocs_session
