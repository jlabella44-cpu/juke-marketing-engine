"""Shared test fixtures for Juke Marketing Engine tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# --- IMAP mock fixture ---
@pytest.fixture
def mock_imap():
    """Mock imaplib.IMAP4_SSL for email detection tests."""
    with patch("app.services.email_detection.imaplib.IMAP4_SSL") as mock_cls:
        imap = MagicMock()
        mock_cls.return_value = imap
        imap.login.return_value = ("OK", [b"LOGIN OK"])
        imap.select.return_value = ("OK", [b"1"])
        imap.search.return_value = ("OK", [b""])
        imap.logout.return_value = ("OK", [b"BYE"])
        yield imap

# --- Anthropic mock fixture ---
@pytest.fixture
def mock_anthropic():
    """Mock anthropic.Anthropic for image tagging tests."""
    with patch("app.services.image_tagging.anthropic.Anthropic") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client

# --- Dropbox mock fixture ---
@pytest.fixture
def mock_dropbox():
    """Mock dropbox.Dropbox for future storage tests."""
    with patch("app.services.dropbox_storage.dropbox") as mock_module:
        dbx = MagicMock()
        mock_module.Dropbox.return_value = dbx
        yield dbx

# --- Test project factory ---
@pytest.fixture
def make_project():
    """Factory fixture to create Project-like dicts for tests."""
    def _make(status="new", **kwargs):
        defaults = {
            "id": uuid4(),
            "address": "123 Main St, Kansas City, MO 64111",
            "slug": "123-main-st-kansas-city-mo-64111",
            "delivery_url": "https://showandtour.com/gallery/abc123",
            "zip_url": "https://showandtour.com/gallery/abc123",
            "email_uid": f"uid_{uuid4().hex[:8]}",
            "status": status,
            "error_stage": None,
            "error_message": None,
        }
        defaults.update(kwargs)
        return defaults
    return _make
