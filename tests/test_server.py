"""Tests for the server as a whole: its curated tools, their safety hints, errors and startup."""

import httpx2
import pytest
from mcp import Client

from crowdsmart_mcp import server
from tests.helpers import FakeApi, call_tool, error_text

pytestmark = pytest.mark.anyio

KNOWLEDGE_AGENT_TOOLS = {
    "list_my_communities",
    "list_knowledge_agents",
    "create_knowledge_agent",
    "update_knowledge_agent",
    "set_knowledge_agent_visibility",
    "ask_knowledge_agent",
    "list_documents",
    "read_document",
    "upload_document",
    "get_document_status",
    "add_text_document",
    "delete_document",
    "check_corpus_quality",
}
JAM_TOOLS = {
    "list_jams",
    "get_jam",
    "create_jam",
    "launch_jam",
    "add_agents_to_jam",
    "get_jam_results",
    "get_jam_responses",
}

READ_ONLY = {
    "list_my_communities",
    "list_knowledge_agents",
    "list_documents",
    "read_document",
    "get_document_status",
    "check_corpus_quality",
    "list_jams",
    "get_jam",
    "get_jam_results",
    "get_jam_responses",
}
DESTRUCTIVE = {
    "update_knowledge_agent",
    "set_knowledge_agent_visibility",
    "delete_document",
}


async def test_server_offers_only_the_curated_tools():
    async with Client(server.mcp) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert set(tools) == KNOWLEDGE_AGENT_TOOLS | JAM_TOOLS
    hints = {
        name: tool.annotations
        for name, tool in tools.items()
        if tool.annotations is not None
    }
    assert set(hints) == set(tools)
    assert {name for name, hint in hints.items() if hint.read_only_hint} == READ_ONLY
    destructive = {name for name, hint in hints.items() if hint.destructive_hint}
    assert destructive == DESTRUCTIVE


async def test_every_request_sends_the_api_key(api: FakeApi):
    routes, requests = api
    routes["GET", "/api/collaborations/active"] = httpx2.Response(
        200, json={"collaborations": []}
    )

    _ = await call_tool("list_jams")

    assert {request.headers["Authorization"] for request in requests} == {
        "Bearer crc_test"
    }


async def test_api_errors_reach_the_client(api: FakeApi):
    routes, _ = api
    routes["GET", "/api/knowledge-agents/a1/documents"] = httpx2.Response(
        403, json={"detail": "Not authorized to access this knowledge agent"}
    )

    result = await call_tool("list_documents", agent_id="a1")

    assert error_text(result).endswith(
        "CrowdSmart API error 403: Not authorized to access this knowledge agent"
    )


async def test_validation_errors_name_the_field(api: FakeApi):
    routes, _ = api
    routes["POST", "/api/knowledge-agents/a1/text"] = httpx2.Response(
        422,
        json={
            "detail": [
                {"loc": ["body", "title"], "msg": "Field required"},
                {"loc": ["body", "text"], "msg": "Input should be a string"},
            ]
        },
    )

    result = await call_tool("add_text_document", agent_id="a1", title="t", text="x")

    assert error_text(result).endswith(
        "CrowdSmart API error 422: body.title: Field required; body.text: Input should be a string"
    )


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (
            httpx2.Response(200, text="<html>login</html>"),
            "not JSON: <html>login</html>",
        ),
        (
            httpx2.Response(307, headers={"location": "/elsewhere"}),
            "CrowdSmart API error 307",
        ),
        (httpx2.Response(422, json={"detail": ["bad input"]}), "bad input"),
    ],
)
async def test_unexpected_responses_are_reported(
    api: FakeApi, reply: httpx2.Response, message: str
):
    routes, requests = api
    routes["GET", "/api/knowledge-agents/a1/documents"] = reply

    result = await call_tool("list_documents", agent_id="a1")

    assert message in error_text(result)
    assert len(requests) == 1  # a redirect is not followed


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        (
            "ask_knowledge_agent",
            {"agent_id": "../human-auth/api-key#", "question": "q"},
        ),
        (
            "delete_document",
            {"agent_id": "a1", "document_id": "../../a1?force_delete=true"},
        ),
        ("delete_document", {"agent_id": "a1?force_delete=true#", "document_id": "d1"}),
        ("list_documents", {"agent_id": "a1%2F..%2F"}),
        ("launch_jam", {"jam_id": "j1/../../human-auth/api-key"}),
        ("read_document", {"agent_id": "a1", "document_id": "d1", "max_chars": -1}),
    ],
)
async def test_invalid_arguments_send_no_request(
    api: FakeApi, tool: str, arguments: dict[str, object]
):
    _, requests = api

    result = await call_tool(tool, **arguments)

    assert result.is_error
    assert requests == []


async def test_unreachable_api_is_reported(api: FakeApi):
    routes, _ = api
    routes["GET", "/api/knowledge-agents/a1/documents"] = httpx2.ConnectError(
        "Connection refused"
    )

    result = await call_tool("list_documents", agent_id="a1")

    assert "Could not reach CrowdSmart" in error_text(result)


def test_main_exits_without_an_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CROWDSMART_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exit_info:
        server.main()

    assert "CROWDSMART_API_KEY" in str(exit_info.value.code)
