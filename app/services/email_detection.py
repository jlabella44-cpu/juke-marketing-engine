import email
import imaplib
import logging
import re

from app.config import settings

logger = logging.getLogger(__name__)


def _extract_address(subject: str) -> str | None:
    """Extract property address from email subject line.

    Expected format: 'Show & Tour Delivery: 123 Main St, Kansas City, MO 64111'
    Returns everything after the first ': ' (colon + space), stripped.
    If no colon or result is empty string, returns None.
    """
    if ":" not in subject:
        return None
    result = subject.split(":", 1)[1].strip()
    return result if result else None


def _extract_zip_url(msg: email.message.Message) -> str | None:
    """Extract first HTTP(S) URL from the email body.

    If the message is multipart, searches the text/plain part.
    Returns the first URL match, or None if not found.
    """
    body_text = None

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_text = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")

    if not body_text:
        return None

    match = re.search(r"https?://[^\s<>\"]+", body_text)
    return match.group(0) if match else None


def poll_inbox() -> list[dict]:
    """Poll IMAP inbox, return list of unprocessed delivery emails.

    Returns:
        List of dicts with keys: email_uid, address, zip_url, delivery_url.

    Raises:
        imaplib.IMAP4.error: On IMAP connection/auth/protocol errors (caller handles retry).

    Pre-insert validation:
        address and zip_url must be non-None non-empty strings.
        If parsing fails, logs a warning and skips the email (no project created).
    """
    results: list[dict] = []

    imap = imaplib.IMAP4_SSL(settings.IMAP_HOST, settings.IMAP_PORT)
    try:
        imap.login(settings.IMAP_USERNAME, settings.IMAP_PASSWORD)
        imap.select(settings.IMAP_MAILBOX)

        _status, uid_data = imap.search(None, "UNSEEN")
        uid_list = uid_data[0].split() if uid_data and uid_data[0] else []

        for uid in uid_list:
            try:
                _fetch_status, msg_data = imap.fetch(uid, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    logger.warning("Empty fetch response for UID %s, skipping", uid)
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = msg.get("Subject", "") or ""
                address = _extract_address(subject)
                zip_url = _extract_zip_url(msg)

                if not address:
                    logger.warning("UID %s: address is empty (subject=%r), skipping", uid, subject)
                    continue

                if not zip_url:
                    logger.warning("UID %s: no URL found in body (subject=%r), skipping", uid, subject)
                    continue

                imap.store(uid, "+FLAGS", "\\Seen")

                results.append(
                    {
                        "email_uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                        "address": address,
                        "zip_url": zip_url,
                        "delivery_url": zip_url,
                    }
                )

            except imaplib.IMAP4.error:
                raise
            except Exception:
                logger.error("UID %s: unexpected error parsing email, skipping", uid, exc_info=True)
                continue

    finally:
        try:
            imap.logout()
        except Exception:
            pass

    return results
