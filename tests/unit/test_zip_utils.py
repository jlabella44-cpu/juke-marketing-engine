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


def test_zipslip_sibling_prefix_rejected(tmp_path):
    """Sibling directory with same prefix as target must be rejected."""
    zip_path = tmp_path / "evil.zip"
    # Create a path that starts with target_dir name but is a sibling
    # We simulate this by manually crafting a ZipInfo entry
    import zipfile
    zf = zipfile.ZipFile(zip_path, 'w')
    # Write a file that when joined to target would resolve outside
    info = zipfile.ZipInfo("../sibling-evil/payload.txt")
    zf.writestr(info, "evil content")
    zf.close()
    target = tmp_path / "output"
    with pytest.raises(ValueError, match="zipslip"):
        safe_extract(zip_path, target)


def test_directory_entries_skipped(tmp_path):
    """safe_extract should skip directory-only entries."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.mkdir("emptydir")  # directory entry only, no files
    target = tmp_path / "output"
    safe_extract(zip_path, target)
    # Directory entry should be skipped — no empty dir created
    assert not (target / "emptydir").exists()
