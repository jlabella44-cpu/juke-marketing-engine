"""Unit tests for FastAPI endpoints — auth, routing, and response shape."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.main import create_app
from app.database import get_db


@pytest.fixture
def test_app():
    return create_app()


@pytest.fixture
def api_key():
    return "test-api-key"


@pytest.fixture(autouse=True)
def mock_settings(api_key):
    with patch("app.api.deps.settings") as mock:
        mock.API_KEY = api_key
        yield mock


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_api_key_returns_401(test_app):
    """No X-API-Key header → 401."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/projects")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wrong_api_key_returns_401(test_app, api_key):
    """Wrong X-API-Key value → 401."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/projects", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check_returns_200_structure(test_app):
    """GET /api/health — no auth required, returns {status, db, redis}."""
    with patch("app.api.health.engine") as mock_engine, \
         patch("app.api.health.redis") as mock_redis:
        # Mock DB connection success
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_engine.connect.return_value = mock_conn

        # Mock Redis ping success
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        mock_redis.Redis.from_url.return_value = mock_redis_client

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "db" in data
    assert "redis" in data


# ---------------------------------------------------------------------------
# GET /api/projects — pagination shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_projects_pagination_shape(test_app, api_key):
    """Valid API key + mocked empty DB → response has items, total, page, page_size."""
    mock_db = AsyncMock()

    # First execute: count query → scalar_one() = 0
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0

    # Second execute: list query → scalars().all() = []
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[count_result, list_result])

    async def override_get_db():
        yield mock_db

    test_app.dependency_overrides[get_db] = override_get_db

    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get("/api/projects", headers={"X-API-Key": api_key})
    finally:
        test_app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["page_size"] == 20


# ---------------------------------------------------------------------------
# GET /api/projects/{id} — 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_project_not_found_returns_404(test_app, api_key):
    """Non-existent project ID → 404."""
    mock_db = AsyncMock()
    none_result = MagicMock()
    none_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=none_result)

    async def override_get_db():
        yield mock_db

    test_app.dependency_overrides[get_db] = override_get_db

    try:
        project_id = uuid4()
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                f"/api/projects/{project_id}",
                headers={"X-API-Key": api_key},
            )
    finally:
        test_app.dependency_overrides.clear()

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/projects/{id}/reprocess — 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reprocess_project_not_found_returns_404(test_app, api_key):
    """Non-existent project ID → 404."""
    mock_db = AsyncMock()
    none_result = MagicMock()
    none_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=none_result)

    async def override_get_db():
        yield mock_db

    test_app.dependency_overrides[get_db] = override_get_db

    try:
        project_id = uuid4()
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post(
                f"/api/projects/{project_id}/reprocess",
                headers={"X-API-Key": api_key},
            )
    finally:
        test_app.dependency_overrides.clear()

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/projects/{id}/photos — 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_project_photos_not_found_returns_404(test_app, api_key):
    """Non-existent project ID → 404."""
    mock_db = AsyncMock()
    none_result = MagicMock()
    none_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=none_result)

    async def override_get_db():
        yield mock_db

    test_app.dependency_overrides[get_db] = override_get_db

    try:
        project_id = uuid4()
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.get(
                f"/api/projects/{project_id}/photos",
                headers={"X-API-Key": api_key},
            )
    finally:
        test_app.dependency_overrides.clear()

    assert response.status_code == 404
