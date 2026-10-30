"""Shared test helpers: the in-process MCP client, and readers for the fake API's requests."""

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx2
from mcp import Client
from mcp.types import CallToolResult, TextContent

from crowdsmart_mcp import server

USER_ID = "user-1"
ME = {"user_id": USER_ID, "name": "Ada Lovelace", "email": "ada@example.com"}

# A route answers with a response, raises an exception, or works out its
# response from the request (for example from its query parameters).
Reply = httpx2.Response | Exception | Callable[[httpx2.Request], httpx2.Response]
Routes = dict[tuple[str, str], Reply]
FakeApi = tuple[Routes, list[httpx2.Request]]


def ok(payload: Mapping[str, object] | Sequence[object]) -> httpx2.Response:
    """A successful API response with this JSON body."""
    return httpx2.Response(200, json=payload)


async def call_tool(tool: str, **arguments: object) -> CallToolResult:
    """Call a tool through an MCP client connected to the server in process."""
    async with Client(server.mcp) as client:
        return await client.call_tool(tool, arguments)


def error_text(result: CallToolResult) -> str:
    assert result.is_error
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


def sent(requests: list[httpx2.Request], method: str, path: str) -> Any:
    """The JSON body of the one request that the server sent to (method, path)."""
    (request,) = [r for r in requests if (r.method, r.url.path) == (method, path)]
    return json.loads(request.content)
