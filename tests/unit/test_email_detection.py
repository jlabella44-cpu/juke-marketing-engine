"""Unit tests for app.services.email_detection.poll_inbox()."""
import imaplib
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_detection import poll_inbox


def _make_raw_email(subject: str | None = None, body: str | None = None) -> bytes:
    """Helper: build a raw RFC822 email bytes object."""
    msg = EmailMessage()
    if subject is not None:
        msg["Subject"] = subject
    msg["From"] = "delivery@showandtour.com"
    msg["To"] = "automation@jukemediakc.com"
    if body is not None:
        msg.set_content(body)
    return msg.as_bytes()


def _build_imap_mock(raw_emails: list[bytes]) -> MagicMock:
    """Return a mock IMAP4_SSL instance that yields the given raw email bytes."""
    imap = MagicMock()

    # search() returns space-separated byte UIDs
    uid_bytes = b" ".join(str(i + 1).encode() for i in range(len(raw_emails)))
    imap.search.return_value = ("OK", [uid_bytes])

    # fetch() returns data in the expected nested structure
    def fake_fetch(uid, spec):
        idx = int(uid) - 1
        raw = raw_emails[idx]
        return ("OK", [(b"1 (RFC822 {%d}" % len(raw), raw)])

    imap.fetch.side_effect = fake_fetch
    imap.store.return_value = ("OK", [b"1"])
    imap.select.return_value = ("OK", [b"1"])
    imap.login.return_value = ("OK", [b"Logged in"])
    imap.logout.return_value = ("BYE", [b"Logout"])

    return imap


# ---------------------------------------------------------------------------
# Test 1: Success — one valid email → one result dict
# ---------------------------------------------------------------------------
@patch("app.services.email_detection.imaplib.IMAP4_SSL")
def test_poll_inbox_success(mock_imap_cls):
    raw = _make_raw_email(
        subject="Show & Tour Delivery: 123 Main St, Kansas City, MO 64111",
        body="Download your gallery: https://showandtour.com/gallery/abc123",
    )
    imap_instance = _build_imap_mock([raw])
    mock_imap_cls.return_value = imap_instance

    results = poll_inbox()

    assert len(results) == 1
    r = results[0]
    assert r["email_uid"] == "1"
    assert r["address"] == "123 Main St, Kansas City, MO 64111"
    assert r["zip_url"] == "https://showandtour.com/gallery/abc123"
    assert r["delivery_url"] == r["zip_url"]

    imap_instance.store.assert_called_once_with(b"1", "+FLAGS", "\\Seen")


# ---------------------------------------------------------------------------
# Test 2: IMAP error on login → exception propagates to caller
# ---------------------------------------------------------------------------
@patch("app.services.email_detection.imaplib.IMAP4_SSL")
def test_poll_inbox_imap_error_propagates(mock_imap_cls):
    imap_instance = MagicMock()
    imap_instance.login.side_effect = imaplib.IMAP4.error("AUTH failed")
    mock_imap_cls.return_value = imap_instance

    with pytest.raises(imaplib.IMAP4.error):
        poll_inbox()

    imap_instance.logout.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3: No address (empty subject) → skip, return empty list
# ---------------------------------------------------------------------------
@patch("app.services.email_detection.imaplib.IMAP4_SSL")
def test_poll_inbox_empty_subject_skipped(mock_imap_cls):
    # Subject with no colon and empty content → address will be empty string
    raw = _make_raw_email(
        subject="",
        body="Download: https://showandtour.com/gallery/abc123",
    )
    imap_instance = _build_imap_mock([raw])
    mock_imap_cls.return_value = imap_instance

    results = poll_inbox()

    assert results == []
    imap_instance.store.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: No URL in body → skip, return empty list
# ---------------------------------------------------------------------------
@patch("app.services.email_detection.imaplib.IMAP4_SSL")
def test_poll_inbox_no_url_in_body_skipped(mock_imap_cls):
    raw = _make_raw_email(
        subject="Show & Tour Delivery: 456 Oak Ave, Overland Park, KS 66210",
        body="Your gallery is being prepared. No link available yet.",
    )
    imap_instance = _build_imap_mock([raw])
    mock_imap_cls.return_value = imap_instance

    results = poll_inbox()

    assert results == []
    imap_instance.store.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: URL with trailing punctuation → stripped correctly
# ---------------------------------------------------------------------------
@patch("app.services.email_detection.imaplib.IMAP4_SSL")
def test_poll_inbox_url_trailing_punctuation_stripped(mock_imap_cls):
    """URL with trailing period in body is cleaned correctly."""
    raw = _make_raw_email(
        subject="Show & Tour Delivery: 456 Oak Ave, KC",
        body="Download your gallery here: https://showandtour.com/gallery/xyz789.",
    )
    imap_instance = _build_imap_mock([raw])
    mock_imap_cls.return_value = imap_instance

    results = poll_inbox()

    assert len(results) == 1
    assert results[0]["zip_url"] == "https://showandtour.com/gallery/xyz789"
    assert not results[0]["zip_url"].endswith(".")
