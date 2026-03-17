"""Unit tests for app.services.media_ingestion.process()."""
import errno
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.services.media_ingestion import process


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(status: str = "new", zip_url: str = "https://example.com/source.zip"):
    """Return a mock Project ORM object."""
    project = MagicMock()
    project.id = uuid4()
    project.status = status
    project.zip_url = zip_url
    return project


def _make_db_mock(project):
    """Return a mock async DB session whose execute() returns the given project."""
    db = AsyncMock()

    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = project
    db.execute.return_value = scalar_result

    return db


def _make_session_ctx(db_mock):
    """Wrap db_mock in an async context manager so async_session_factory() works."""
    session_ctx = AsyncMock()
    session_ctx.__aenter__.return_value = db_mock
    session_ctx.__aexit__.return_value = False
    return session_ctx


def _make_streaming_response(status_code: int = 200, chunks: list[bytes] | None = None):
    """Return a mock httpx streaming response usable as an async context manager."""
    if chunks is None:
        chunks = [b"fake zip data"]

    async def _aiter_bytes(chunk_size=8192):
        for chunk in chunks:
            yield chunk

    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    response.aiter_bytes = _aiter_bytes

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__.return_value = response
    stream_ctx.__aexit__.return_value = False
    return stream_ctx


def _make_http_client_mock(stream_ctx):
    """Return a mock httpx.AsyncClient whose .stream() returns stream_ctx."""
    client = AsyncMock()
    client.stream.return_value = stream_ctx

    client_ctx = AsyncMock()
    client_ctx.__aenter__.return_value = client
    client_ctx.__aexit__.return_value = False
    return client_ctx


# ---------------------------------------------------------------------------
# Test 1: HTTP 4xx → FAILED with error_stage="ingestion"
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.media_ingestion.async_session_factory")
@patch("app.services.media_ingestion.httpx.AsyncClient")
@patch("app.services.media_ingestion.set_project_status", new_callable=AsyncMock)
async def test_http_4xx_sets_failed(mock_set_status, mock_client_cls, mock_session_factory):
    project = _make_project(status="new")
    db = _make_db_mock(project)
    mock_session_factory.return_value = _make_session_ctx(db)

    # Build a 404 HTTPStatusError
    mock_response = MagicMock()
    mock_response.status_code = 404
    http_error = httpx.HTTPStatusError(
        message="Not Found",
        request=MagicMock(),
        response=mock_response,
    )

    stream_ctx = AsyncMock()
    stream_ctx.__aenter__.side_effect = http_error

    client = AsyncMock()
    client.stream.return_value = stream_ctx

    client_ctx = AsyncMock()
    client_ctx.__aenter__.return_value = client
    client_ctx.__aexit__.return_value = False
    mock_client_cls.return_value = client_ctx

    with pytest.raises(httpx.HTTPStatusError):
        await process(project.id)

    # Verify FAILED status was set with correct stage
    failed_calls = [
        c for c in mock_set_status.call_args_list
        if c.args[2] == "failed"
    ]
    assert len(failed_calls) >= 1
    call_kwargs = failed_calls[-1].kwargs
    assert call_kwargs.get("error_stage") == "ingestion"
    assert "404" in call_kwargs.get("error_message", "")


# ---------------------------------------------------------------------------
# Test 2: Timeout × 3 → FAILED after 3 attempts
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.media_ingestion.async_session_factory")
@patch("app.services.media_ingestion.httpx.AsyncClient")
@patch("app.services.media_ingestion.set_project_status", new_callable=AsyncMock)
@patch("app.services.media_ingestion.asyncio.sleep", new_callable=AsyncMock)
async def test_timeout_retry_then_fail(mock_sleep, mock_set_status, mock_client_cls, mock_session_factory):
    project = _make_project(status="new")
    db = _make_db_mock(project)
    mock_session_factory.return_value = _make_session_ctx(db)

    # Every stream attempt raises TimeoutException
    stream_ctx = AsyncMock()
    stream_ctx.__aenter__.side_effect = httpx.TimeoutException("timed out")

    client = AsyncMock()
    client.stream.return_value = stream_ctx

    client_ctx = AsyncMock()
    client_ctx.__aenter__.return_value = client
    client_ctx.__aexit__.return_value = False
    mock_client_cls.return_value = client_ctx

    with pytest.raises(httpx.TimeoutException):
        await process(project.id)

    # httpx.AsyncClient should have been constructed 3 times (one per attempt)
    assert mock_client_cls.call_count == 3

    # sleep called twice (after attempt 0 and 1, not after final attempt)
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(1)  # 2**0
    mock_sleep.assert_any_call(2)  # 2**1

    # Final status must be FAILED
    failed_calls = [c for c in mock_set_status.call_args_list if c.args[2] == "failed"]
    assert len(failed_calls) >= 1
    assert failed_calls[-1].kwargs.get("error_stage") == "ingestion"
    assert "timeout" in failed_calls[-1].kwargs.get("error_message", "").lower()


# ---------------------------------------------------------------------------
# Test 3: ENOSPC → FAILED + CRITICAL log
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.media_ingestion.async_session_factory")
@patch("app.services.media_ingestion.httpx.AsyncClient")
@patch("app.services.media_ingestion.set_project_status", new_callable=AsyncMock)
@patch("builtins.open")
async def test_enospc_sets_failed_and_logs_critical(
    mock_open, mock_set_status, mock_client_cls, mock_session_factory, caplog
):
    import logging

    project = _make_project(status="new")
    db = _make_db_mock(project)
    mock_session_factory.return_value = _make_session_ctx(db)

    # open() raises ENOSPC
    enospc = OSError(errno.ENOSPC, "No space left on device")
    mock_open.side_effect = enospc

    # mkdir must succeed — patch Path.mkdir so temp_dir creation works
    with patch("pathlib.Path.mkdir"):
        stream_ctx = _make_streaming_response()
        mock_client_cls.return_value = _make_http_client_mock(stream_ctx)

        with caplog.at_level(logging.CRITICAL, logger="app.services.media_ingestion"):
            with pytest.raises(OSError) as exc_info:
                await process(project.id)

    assert exc_info.value.errno == errno.ENOSPC

    # CRITICAL log must have been emitted
    critical_records = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert any("ENOSPC" in r.message for r in critical_records)

    # Status must be FAILED
    failed_calls = [c for c in mock_set_status.call_args_list if c.args[2] == "failed"]
    assert len(failed_calls) >= 1
    assert failed_calls[-1].kwargs.get("error_stage") == "ingestion"


# ---------------------------------------------------------------------------
# Test 4: Invalid image skipped, valid images succeed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.media_ingestion.async_session_factory")
@patch("app.services.media_ingestion.httpx.AsyncClient")
@patch("app.services.media_ingestion.set_project_status", new_callable=AsyncMock)
@patch("app.services.media_ingestion.safe_extract")
@patch("app.services.media_ingestion.validate_image")
async def test_invalid_image_skipped_valid_ingested(
    mock_validate, mock_safe_extract, mock_set_status, mock_client_cls, mock_session_factory, tmp_path
):
    project = _make_project(status="new")
    db = _make_db_mock(project)
    mock_session_factory.return_value = _make_session_ctx(db)

    # Create two fake image files under tmp_path (real files so rglob works)
    images_dir = tmp_path / str(project.id) / "images"
    images_dir.mkdir(parents=True)
    valid_img = images_dir / "valid.jpg"
    invalid_img = images_dir / "corrupt.jpg"
    valid_img.write_bytes(b"fake jpeg data")
    invalid_img.write_bytes(b"not an image")

    # validate_image: False for corrupt, True for valid
    mock_validate.side_effect = lambda path: path.name != "corrupt.jpg"
    mock_safe_extract.return_value = None  # no-op

    stream_ctx = _make_streaming_response()
    mock_client_cls.return_value = _make_http_client_mock(stream_ctx)

    with (
        patch("app.services.media_ingestion.settings") as mock_settings,
        patch("builtins.open", MagicMock()),
        patch("pathlib.Path.mkdir"),
    ):
        mock_settings.TEMP_DIR = str(tmp_path)
        await process(project.id)

    # Ingested status must be set
    ingested_calls = [c for c in mock_set_status.call_args_list if c.args[2] == "ingested"]
    assert len(ingested_calls) == 1

    # Only the valid photo was added
    add_calls = db.add.call_args_list
    assert len(add_calls) == 1
    added_photo = add_calls[0].args[0]
    assert "corrupt.jpg" not in added_photo.file_path


# ---------------------------------------------------------------------------
# Test 5: Idempotency — status "ingested" → return immediately, no HTTP call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@patch("app.services.media_ingestion.async_session_factory")
@patch("app.services.media_ingestion.httpx.AsyncClient")
@patch("app.services.media_ingestion.set_project_status", new_callable=AsyncMock)
async def test_idempotency_already_ingested(mock_set_status, mock_client_cls, mock_session_factory):
    project = _make_project(status="ingested")
    db = _make_db_mock(project)
    mock_session_factory.return_value = _make_session_ctx(db)

    await process(project.id)

    # No HTTP call made
    mock_client_cls.assert_not_called()

    # set_project_status never called (no status transitions)
    mock_set_status.assert_not_called()
