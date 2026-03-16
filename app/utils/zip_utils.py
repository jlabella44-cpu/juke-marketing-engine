import zipfile
from pathlib import Path

def safe_extract(zip_path: Path, target_dir: Path) -> None:
    """
    Extract zip file to target_dir with zipslip protection.

    Iterates all entries. For each entry, resolves the full path and
    rejects any entry whose resolved path escapes target_dir by raising
    ValueError("zipslip").

    Only extracts files (skips directories). Creates target_dir if needed.
    """
    target_dir = Path(target_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            member_path = (target_dir / member).resolve()
            # Zipslip check: resolved path must be inside target_dir
            if not str(member_path).startswith(str(target_dir)):
                raise ValueError("zipslip")
            # Skip directory entries
            if not member.endswith('/'):
                zf.extract(member, target_dir)
