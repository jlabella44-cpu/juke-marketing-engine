import re

def address_to_slug(address: str) -> str:
    """
    Convert a property address to a URL-safe slug.

    Steps:
    1. Lowercase
    2. Replace any character that is not alphanumeric or hyphen with a hyphen
    3. Collapse multiple consecutive hyphens into one
    4. Strip leading and trailing hyphens

    Example: "123 Main St, Kansas City, MO 64111" -> "123-main-st-kansas-city-mo-64111"
    """
    slug = address.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug
