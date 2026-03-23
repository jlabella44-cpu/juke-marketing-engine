"""Property data scraper — fetches listing details from Zillow, Realtor.com, Homes.com.

Uses Playwright sync API via ThreadPoolExecutor (safe for Celery prefork workers).
Cross-references three sources and resolves a confident set of listing data.
"""
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import async_session_factory, set_project_status
from app.models.listing_data import ProjectListingData
from app.models.project import Project

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="scraper")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def process(project_id: UUID) -> None:
    """Idempotent. Skips if listing data already exists. Sets project status scraped/failed."""
    async with async_session_factory() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None or project.status != "ingested":
            logger.info("Skipping scraping for project %s — status=%s", project_id,
                        project.status if project else "not found")
            return

        # Idempotency: skip if already scraped
        existing = await db.execute(
            select(ProjectListingData).where(ProjectListingData.project_id == project_id)
        )
        if existing.scalar_one_or_none() is not None:
            logger.info("Listing data already exists for project %s, skipping", project_id)
            await set_project_status(db, project_id, "scraped")
            await db.commit()
            return

        await set_project_status(db, project_id, "scraping")
        await db.commit()

        address = project.address
        loop = asyncio.get_running_loop()

        # Run all three scrapes concurrently in thread pool
        zillow_fut  = loop.run_in_executor(_executor, _scrape_zillow, address)
        realtor_fut = loop.run_in_executor(_executor, _scrape_realtor, address)
        homes_fut   = loop.run_in_executor(_executor, _scrape_homes, address)

        zillow_data, realtor_data, homes_data = await asyncio.gather(
            zillow_fut, realtor_fut, homes_fut, return_exceptions=True
        )

        # Treat exceptions as None (site unavailable / bot-blocked)
        def _safe(val):
            if isinstance(val, Exception):
                logger.warning("Scrape error: %s", val)
                return None
            return val

        zillow_data  = _safe(zillow_data)
        realtor_data = _safe(realtor_data)
        homes_data   = _safe(homes_data)

        sources = {"zillow": zillow_data, "realtor": realtor_data, "homes": homes_data}
        resolved = _cross_reference(sources)

        def _v(d, k):
            return d.get(k) if d else None

        listing = ProjectListingData(
            project_id=project_id,
            zillow_beds=_v(zillow_data, "beds"),
            zillow_baths=_v(zillow_data, "baths"),
            zillow_sqft=_v(zillow_data, "sqft"),
            zillow_year_built=_v(zillow_data, "year_built"),
            zillow_price=_v(zillow_data, "price"),
            zillow_lot_size=_v(zillow_data, "lot_size"),
            zillow_property_type=_v(zillow_data, "property_type"),
            realtor_beds=_v(realtor_data, "beds"),
            realtor_baths=_v(realtor_data, "baths"),
            realtor_sqft=_v(realtor_data, "sqft"),
            realtor_year_built=_v(realtor_data, "year_built"),
            realtor_price=_v(realtor_data, "price"),
            realtor_lot_size=_v(realtor_data, "lot_size"),
            realtor_property_type=_v(realtor_data, "property_type"),
            homes_beds=_v(homes_data, "beds"),
            homes_baths=_v(homes_data, "baths"),
            homes_sqft=_v(homes_data, "sqft"),
            homes_year_built=_v(homes_data, "year_built"),
            homes_price=_v(homes_data, "price"),
            homes_lot_size=_v(homes_data, "lot_size"),
            homes_property_type=_v(homes_data, "property_type"),
            beds=resolved.get("beds"),
            baths=resolved.get("baths"),
            sqft=resolved.get("sqft"),
            year_built=resolved.get("year_built"),
            price=resolved.get("price"),
            lot_size=resolved.get("lot_size"),
            property_type=resolved.get("property_type"),
            confidence=resolved["confidence"],
            confidence_notes=resolved.get("confidence_notes"),
        )
        db.add(listing)
        await set_project_status(db, project_id, "scraped")
        await db.commit()
        logger.info("Scraped listing data for project %s — confidence=%s", project_id, resolved["confidence"])


# ---------------------------------------------------------------------------
# Cross-reference logic
# ---------------------------------------------------------------------------

def _cross_reference(sources: dict) -> dict:
    """Resolve listing data from up to 3 sources. Returns resolved dict with confidence."""
    active = {k: v for k, v in sources.items() if v is not None}
    if not active:
        return {"confidence": "none", "beds": None, "baths": None, "sqft": None}

    def _agree(key, tolerance=0.05):
        """Return (agrees: bool, value) for a numeric key."""
        vals = [s[key] for s in active.values() if s.get(key) is not None]
        if len(vals) < 2:
            return False, (vals[0] if vals else None)
        base = vals[0]
        if base == 0:
            return all(v == 0 for v in vals), base
        avg = sum(vals) / len(vals)
        agrees = all(abs(v - base) / base <= tolerance for v in vals[1:])
        # Preserve float for non-integer values (e.g. baths); cast to int only when whole number
        rounded = int(avg) if avg == int(avg) else avg
        return agrees, rounded

    beds_ok,  beds  = _agree("beds",  tolerance=0)
    baths_ok, baths = _agree("baths", tolerance=0)
    sqft_ok,  sqft  = _agree("sqft",  tolerance=0.05)

    all_three = len(active) == 3
    two_agree = beds_ok and baths_ok and sqft_ok

    notes = []
    if not beds_ok:
        notes.append(f"beds disagreement: {[s.get('beds') for s in active.values()]}")
    if not baths_ok:
        notes.append(f"baths disagreement: {[s.get('baths') for s in active.values()]}")
    if not sqft_ok:
        notes.append(f"sqft disagreement: {[s.get('sqft') for s in active.values()]}")

    if two_agree and len(active) >= 2:
        confidence = "high" if all_three else "medium"
    elif len(active) == 1:
        confidence = "low"
        notes.append("only one source returned data")
    else:
        confidence = "low"

    # Use the first available value for non-key fields
    def _first(key):
        for s in active.values():
            v = s.get(key)
            if v is not None:
                return v
        return None

    return {
        "confidence": confidence,
        "confidence_notes": "; ".join(notes) if notes else None,
        "beds": beds,
        "baths": baths,
        "sqft": sqft,
        "year_built": _first("year_built"),
        "price": _first("price"),
        "lot_size": _first("lot_size"),
        "property_type": _first("property_type"),
    }


# Alias for test imports
resolve_listing_data = _cross_reference


# ---------------------------------------------------------------------------
# Site-specific scrapers (Playwright sync API)
# ---------------------------------------------------------------------------

def _scrape_zillow(address: str) -> dict | None:
    """Scrape property data from Zillow. Returns dict or None on failure."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            query = address.replace(" ", "+")
            page.goto(f"https://www.zillow.com/homes/{query}_rb/", timeout=20000)
            page.wait_for_timeout(3000)

            try:
                page.click("[data-test='property-card-link']", timeout=5000)
                page.wait_for_timeout(2000)
            except Exception:
                pass

            html = page.content()
            browser.close()

        return _parse_zillow_html(html)
    except Exception as e:
        logger.warning("Zillow scrape failed for %r: %s", address, e)
        return None


def _parse_zillow_html(html: str) -> dict | None:
    """Extract beds/baths/sqft from Zillow HTML."""
    data = {}
    beds_m = re.search(r'(\d+)\s*(?:bd|bed)', html, re.IGNORECASE)
    baths_m = re.search(r'([\d.]+)\s*(?:ba|bath)', html, re.IGNORECASE)
    sqft_m = re.search(r'([\d,]+)\s*sq\s*ft', html, re.IGNORECASE)
    price_m = re.search(r'\$\s*([\d,]+)', html)
    year_m = re.search(r'(?:built in|year built)[:\s]*(\d{4})', html, re.IGNORECASE)

    if beds_m:
        data["beds"] = int(beds_m.group(1))
    if baths_m:
        data["baths"] = float(baths_m.group(1))
    if sqft_m:
        data["sqft"] = int(sqft_m.group(1).replace(",", ""))
    if price_m:
        data["price"] = int(price_m.group(1).replace(",", ""))
    if year_m:
        data["year_built"] = int(year_m.group(1))

    return data if data else None


def _scrape_realtor(address: str) -> dict | None:
    """Scrape property data from Realtor.com."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = ctx.new_page()
            query = address.lower().replace(" ", "-").replace(",", "")
            page.goto(f"https://www.realtor.com/realestateandhomes-search/{query}", timeout=20000)
            page.wait_for_timeout(3000)

            try:
                page.click("[data-testid='card-anchor']", timeout=5000)
                page.wait_for_timeout(2000)
            except Exception:
                pass

            html = page.content()
            browser.close()

        return _parse_generic_html(html)
    except Exception as e:
        logger.warning("Realtor.com scrape failed for %r: %s", address, e)
        return None


def _scrape_homes(address: str) -> dict | None:
    """Scrape property data from Homes.com."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = ctx.new_page()
            query = address.replace(" ", "+")
            page.goto(f"https://www.homes.com/search/?q={query}", timeout=20000)
            page.wait_for_timeout(3000)

            try:
                page.click(".listing-card", timeout=5000)
                page.wait_for_timeout(2000)
            except Exception:
                pass

            html = page.content()
            browser.close()

        return _parse_generic_html(html)
    except Exception as e:
        logger.warning("Homes.com scrape failed for %r: %s", address, e)
        return None


def _parse_generic_html(html: str) -> dict | None:
    """Generic beds/baths/sqft parser for Realtor.com and Homes.com."""
    data = {}
    beds_m = re.search(r'(\d+)\s*(?:bd|bed|bedroom)', html, re.IGNORECASE)
    baths_m = re.search(r'([\d.]+)\s*(?:ba|bath|bathroom)', html, re.IGNORECASE)
    sqft_m = re.search(r'([\d,]+)\s*sq\s*ft', html, re.IGNORECASE)
    price_m = re.search(r'\$\s*([\d,]+)', html)
    year_m = re.search(r'(?:built in|year built)[:\s]*(\d{4})', html, re.IGNORECASE)

    if beds_m:
        data["beds"] = int(beds_m.group(1))
    if baths_m:
        data["baths"] = float(baths_m.group(1))
    if sqft_m:
        data["sqft"] = int(sqft_m.group(1).replace(",", ""))
    if price_m:
        data["price"] = int(price_m.group(1).replace(",", ""))
    if year_m:
        data["year_built"] = int(year_m.group(1))

    return data if data else None
