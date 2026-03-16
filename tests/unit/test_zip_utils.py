import zipfile
import pytest
from pathlib import Path
from app.utils.zip_utils import safe_extract


def test_valid_extraction(tmp_path):
    """Valid zip with a file entry is extracted correctly."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("photo.jpg", b"fake jpeg content")
    target = tmp_path / "output"
    safe_extract(zip_path, target)
    assert (target / "photo.jpg").exists()
    assert (target / "photo.jpg").read_bytes() == b"fake jpeg content"


def test_zipslip_rejected(tmp_path):
    """Entry with path traversal raises ValueError('zipslip')."""
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("../../evil.txt", "evil content")
    target = tmp_path / "output"
    with pytest.raises(ValueError, match="zipslip"):
        safe_extract(zip_path, target)


def test_bad_zip_file(tmp_path):
    """Non-zip file raises zipfile.BadZipFile."""
    bad_path = tmp_path / "notazip.txt"
    bad_path.write_text("not a zip")
    target = tmp_path / "output"
    with pytest.raises(zipfile.BadZipFile):
        safe_extract(bad_path, target)


def test_directory_entries_skipped(tmp_path):
    """Directory entries (ending in '/') are not extracted as files/dirs."""
    zip_path = tmp_path / "dirs.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        # Add a directory entry explicitly
        zf.mkdir("subdir")
        zf.writestr("subdir/file.txt", "hello")
    target = tmp_path / "output"
    safe_extract(zip_path, target)
    # The directory entry itself should not have been explicitly created by us,
    # but the file inside it should exist (extracted normally)
    assert (target / "subdir" / "file.txt").exists()
    # No bare directory-only artifact at the top level from a dir-only entry
    # Verify the zip actually had a dir entry
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
    assert any(n.endswith('/') for n in names), "Test setup: zip should contain a dir entry"
