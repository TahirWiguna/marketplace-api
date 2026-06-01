"""Tests for the hardened AuthClient.

Covers: success, timeout, connection error, invalid token, retry logic.
All tests mock httpx so no real network calls are made.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from app.utils.auth_client import AuthClient
from fastapi import HTTPException


@pytest.fixture
def auth_client():
    return AuthClient()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_data: dict | None = None) -> httpx.Response:
    """Build a fake httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        json=json_data or {},
        request=httpx.Request("GET", "http://auth-service:8000/api/v1/auth/me"),
    )
    return resp


def _make_async_client(responses: list):
    """Return a mock httpx.AsyncClient that yields responses in order.

    Each entry in *responses* is either:
      - an httpx.Response  (returned as-is)
      - an Exception subclass  (raised on that call)
    """
    call_index = {"i": 0}

    class MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, headers=None):
            idx = call_index["i"]
            call_index["i"] += 1
            entry = responses[idx]
            if isinstance(entry, type) and issubclass(entry, Exception):
                raise entry("mocked")
            if isinstance(entry, Exception):
                raise entry
            return entry

    return MockAsyncClient


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_token_success(auth_client):
    """Happy path — 200 from auth-service returns user dict."""
    user_data = {"id": "u1", "email": "a@b.com", "username": "alice"}
    mock_client_cls = _make_async_client([_mock_response(200, user_data)])

    with patch("app.utils.auth_client.httpx.AsyncClient", mock_client_cls):
        result = await auth_client.verify_token("good-token")

    assert result == user_data


@pytest.mark.asyncio
async def test_verify_token_invalid_returns_401(auth_client):
    """401 from auth-service raises HTTPException(401)."""
    mock_client_cls = _make_async_client([_mock_response(401)])

    with patch("app.utils.auth_client.httpx.AsyncClient", mock_client_cls):
        with pytest.raises(HTTPException) as exc_info:
            await auth_client.verify_token("bad-token")

    assert exc_info.value.status_code == 401
    assert "Invalid or expired token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_token_timeout_returns_503(auth_client):
    """Timeout on all attempts results in 503."""
    responses = [
        httpx.ReadTimeout("mocked"),
        httpx.ReadTimeout("mocked"),
        httpx.ReadTimeout("mocked"),
        httpx.ReadTimeout("mocked"),
    ]
    mock_client_cls = _make_async_client(responses)

    with patch("app.utils.auth_client.httpx.AsyncClient", mock_client_cls):
        with patch("app.utils.auth_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await auth_client.verify_token("token")

    assert exc_info.value.status_code == 503
    assert "unavailable" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_verify_token_connection_error_returns_503(auth_client):
    """ConnectionError on all attempts results in 503 (not 500)."""
    responses = [
        httpx.ConnectError("connection refused"),
        httpx.ConnectError("connection refused"),
        httpx.ConnectError("connection refused"),
        httpx.ConnectError("connection refused"),
    ]
    mock_client_cls = _make_async_client(responses)

    with patch("app.utils.auth_client.httpx.AsyncClient", mock_client_cls):
        with patch("app.utils.auth_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await auth_client.verify_token("token")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_verify_token_retry_succeeds_on_third_attempt(auth_client):
    """Fail twice (ConnectError), succeed on third attempt."""
    user_data = {"id": "u1", "email": "a@b.com", "username": "alice"}
    responses = [
        httpx.ConnectError("refused"),
        httpx.ConnectError("refused"),
        _mock_response(200, user_data),
    ]
    mock_client_cls = _make_async_client(responses)

    with patch("app.utils.auth_client.httpx.AsyncClient", mock_client_cls):
        with patch("app.utils.auth_client.asyncio.sleep", new_callable=AsyncMock):
            result = await auth_client.verify_token("token")

    assert result == user_data


@pytest.mark.asyncio
async def test_verify_token_retry_on_server_error(auth_client):
    """5xx from auth-service triggers retry; succeeds eventually."""
    user_data = {"id": "u2", "email": "b@b.com"}
    responses = [
        _mock_response(500),
        _mock_response(502),
        _mock_response(200, user_data),
    ]
    mock_client_cls = _make_async_client(responses)

    with patch("app.utils.auth_client.httpx.AsyncClient", mock_client_cls):
        with patch("app.utils.auth_client.asyncio.sleep", new_callable=AsyncMock):
            result = await auth_client.verify_token("token")

    assert result == user_data


@pytest.mark.asyncio
async def test_verify_token_401_not_retried(auth_client):
    """401 is definitive — should NOT trigger retries."""
    call_count = {"n": 0}

    class CountingClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, headers=None):
            call_count["n"] += 1
            return _mock_response(401)

    with patch("app.utils.auth_client.httpx.AsyncClient", CountingClient):
        with pytest.raises(HTTPException) as exc_info:
            await auth_client.verify_token("bad")

    assert exc_info.value.status_code == 401
    assert call_count["n"] == 1, "401 should not trigger retries"


@pytest.mark.asyncio
async def test_verify_token_all_retries_exhausted_server_error(auth_client):
    """All attempts return 503 → final 503 after retries."""
    responses = [_mock_response(503)] * 4  # 1 initial + 3 retries
    mock_client_cls = _make_async_client(responses)

    with patch("app.utils.auth_client.httpx.AsyncClient", mock_client_cls):
        with patch("app.utils.auth_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await auth_client.verify_token("token")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_verify_token_exponential_backoff(auth_client):
    """Verify sleep is called with exponentially increasing delays."""
    sleep_calls = []

    async def mock_sleep(delay):
        sleep_calls.append(delay)

    user_data = {"id": "u1"}
    responses = [
        httpx.ConnectError("refused"),
        httpx.ConnectError("refused"),
        httpx.ConnectError("refused"),
        _mock_response(200, user_data),
    ]
    mock_client_cls = _make_async_client(responses)

    with patch("app.utils.auth_client.httpx.AsyncClient", mock_client_cls):
        with patch("app.utils.auth_client.asyncio.sleep", side_effect=mock_sleep):
            result = await auth_client.verify_token("token")

    assert result == user_data
    assert sleep_calls == [1.0, 2.0, 4.0], f"Expected exponential backoff [1,2,4], got {sleep_calls}"
