"""The fake CrowdSmart API that the tests put behind the server's HTTP client."""

import functools

import httpx2
import pytest

from tests.helpers import ME, FakeApi, Routes


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> FakeApi:
    """Send the server's HTTP requests to a fake API.

    Returns (routes, requests): map (method, path) to an httpx2.Response or an
    exception to raise. Every request the server sends is appended to requests.
    The key's account (GET /api/human-auth/me) is ME unless a test changes it.
    """
    monkeypatch.setenv("CROWDSMART_API_KEY", "crc_test")
    routes: Routes = {("GET", "/api/human-auth/me"): httpx2.Response(200, json=ME)}
    requests: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        _ = request.read()  # a multipart body is streamed until read
        requests.append(request)
        reply = routes[request.method, request.url.path]
        if isinstance(reply, Exception):
            raise reply
        if not isinstance(reply, httpx2.Response):
            reply = reply(request)
        # A fresh copy, so a route can answer more than one request.
        return httpx2.Response(
            reply.status_code, headers=reply.headers, content=reply.read()
        )

    fake_client = functools.partial(
        httpx2.AsyncClient, transport=httpx2.MockTransport(handle)
    )
    monkeypatch.setattr(httpx2, "AsyncClient", fake_client)
    return routes, requests
