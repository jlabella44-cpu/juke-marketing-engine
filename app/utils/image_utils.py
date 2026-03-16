from pathlib import Path
from PIL import Image, UnidentifiedImageError

def validate_image(path: Path) -> bool:
    """
    Validate image file using PIL magic byte verification.

    Opens the file and calls PIL's verify() method which checks magic bytes.
    Returns True if valid, False if PIL.UnidentifiedImageError is raised.
    Does NOT load pixel data — only verifies the file header.
    """
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except UnidentifiedImageError:
        return False
