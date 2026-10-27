"""UK postcode to county and region lookup for the hemp farmer form.

Three sources, tried in order:

1. ``uk_postcode_cache`` - a postcode resolved once is not resolved again.
2. postcodes.io - free, no API key, 3 second timeout.
3. The postcode-area table in ``module_2/data/uk_postcode_areas.json`` - a coarse
   fallback so the officer is never blocked by a network problem.

If all three fail the result carries ``source = "unresolved"`` and ``editable = True``,
which is the only state where the form lets the officer type the county and region.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from module_2.repository import PostcodeCacheRepository
from module_2.services.validators import normalise_postcode, postcode_area

logger = logging.getLogger("sawie.module_2.postcode")

POSTCODES_IO_URL = "https://api.postcodes.io/postcodes/{postcode}"
LOOKUP_TIMEOUT_SECONDS = 3.0

SOURCE_CACHE = "cache"
SOURCE_API = "postcodes_io"
SOURCE_AREA_TABLE = "area_table"
SOURCE_UNRESOLVED = "unresolved"

_DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "uk_postcode_areas.json"


@dataclass(frozen=True)
class PostcodeLocation:
    """Where a postcode is, and how confident we are about it."""

    postcode: str
    county: str | None
    region: str | None
    source: str

    @property
    def resolved(self) -> bool:
        return self.source != SOURCE_UNRESOLVED

    @property
    def editable(self) -> bool:
        """County and region may only be typed by hand when nothing could resolve them."""
        return not self.resolved


@lru_cache(maxsize=1)
def area_table() -> dict[str, tuple[str, str]]:
    """``{"CB": ("Cambridgeshire", "East of England"), ...}`` from the bundled table."""
    document = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    return {row["area"]: (row["county"], row["region"]) for row in document["items"]}


def _from_area_table(postcode: str) -> PostcodeLocation | None:
    entry = area_table().get(postcode_area(postcode))
    if entry is None:
        return None
    county, region = entry
    return PostcodeLocation(
        postcode=postcode, county=county, region=region, source=SOURCE_AREA_TABLE
    )


def fetch_from_api(postcode: str, *, client: httpx.Client | None = None) -> PostcodeLocation | None:
    """Ask postcodes.io. Returns ``None`` on any failure; never raises."""
    url = POSTCODES_IO_URL.format(postcode=postcode.replace(" ", ""))
    try:
        if client is not None:
            response = client.get(url, timeout=LOOKUP_TIMEOUT_SECONDS)
        else:
            with httpx.Client(timeout=LOOKUP_TIMEOUT_SECONDS) as owned:
                response = owned.get(url)
        if response.status_code != 200:
            logger.info("Postcode lookup for %s returned %s", postcode, response.status_code)
            return None
        result = response.json().get("result") or {}
    except Exception as exc:  # noqa: BLE001 - a lookup failure must never fail a request
        logger.info("Postcode lookup for %s failed: %s", postcode, exc)
        return None

    # admin_county is null for unitary authorities, where admin_district is the
    # meaningful name. region is null outside England, where country is.
    county = result.get("admin_county") or result.get("admin_district")
    region = result.get("region") or result.get("country")
    if not county and not region:
        return None
    return PostcodeLocation(postcode=postcode, county=county, region=region, source=SOURCE_API)


def online_lookup_enabled() -> bool:
    """True when postcodes.io may be called (Settings: validation.postcode_lookup_enabled)."""
    from core import app_settings

    return bool(app_settings.setting_or("validation.postcode_lookup_enabled", True))


class PostcodeService:
    """Cache-aware postcode lookup. Writes to the cache but never commits."""

    def __init__(self, session: Session, *, client: httpx.Client | None = None) -> None:
        self.session = session
        self.cache = PostcodeCacheRepository(session)
        self._client = client

    def lookup(self, raw_postcode: str, *, use_cache: bool = True) -> PostcodeLocation:
        postcode = normalise_postcode(raw_postcode)

        if use_cache:
            cached = self.cache.get_by_postcode(postcode)
            if cached is not None:
                return PostcodeLocation(
                    postcode=postcode,
                    county=cached.county,
                    region=cached.region,
                    source=SOURCE_CACHE,
                )

        # Settings can turn the online lookup off; the bundled area table still answers.
        found = None
        if online_lookup_enabled():
            found = fetch_from_api(postcode, client=self._client)
        found = found or _from_area_table(postcode)
        if found is None:
            return PostcodeLocation(
                postcode=postcode, county=None, region=None, source=SOURCE_UNRESOLVED
            )

        self.cache.upsert(postcode, county=found.county, region=found.region, source=found.source)
        return found
