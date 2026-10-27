"""The configuration the browser is allowed to know, and the two test buttons.

Every map in the product (Register Farmer, Harvest Radar, the Dashboard overview, the
public trace page) used to carry its own tile URL and attribution. They now read this
one endpoint, so changing the provider in Settings changes every map at once and the
attribution a tile licence requires can never drift between screens.

Only definitions marked ``public`` and not ``sensitive`` are included, so adding a
setting never leaks it to the browser by accident.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy.orm import Session

from core import app_settings
from module_8 import registry

#: How long the browser may hold the public config. Short: a tile change should show up
#: on the next page view, not after a cache expiry nobody can explain.
CACHE_SECONDS: Final = 60

#: What a tile check asks for: zoom 1, the tile that covers most of the world.
PROBE_TILE: Final = {"z": 1, "x": 1, "y": 1}

_TIMEOUT: Final = 6.0


def tile_layer(session: Session | None = None) -> dict[str, Any]:
    """The chosen provider as Leaflet needs it: URL, attribution, maximum zoom."""
    chosen = str(app_settings.setting_or("map.tile_provider", "esri_imagery", session))
    provider = dict(registry.TILE_PROVIDERS.get(chosen, registry.TILE_PROVIDERS["esri_imagery"]))
    if chosen == "custom":
        provider["url"] = str(app_settings.setting_or("map.custom_tile_url", "", session) or "")
        provider["attribution"] = str(
            app_settings.setting_or("map.custom_attribution", "", session) or ""
        )
        if not provider["url"]:
            # A custom provider with no URL would render an empty map; fall back and say so.
            fallback = dict(registry.TILE_PROVIDERS["esri_imagery"])
            fallback["fallback_reason"] = (
                "Custom tiles are selected but no tile URL is set, so Esri imagery is used."
            )
            return {"key": "esri_imagery", **fallback}
    return {"key": chosen, **provider}


def public_config(session: Session | None = None) -> dict[str, Any]:
    """Everything the web app needs before it can draw a screen."""
    values = app_settings.resolve_all(session, public_only=True)
    return {
        "settings": values,
        "map": {
            "tiles": tile_layer(session),
            "labels_overlay": bool(app_settings.setting_or("map.labels_overlay", False, session)),
            "labels_overlay_url": registry.LABELS_OVERLAY_URL,
            "centres": app_settings.setting_or(
                "map.default_centres", registry.DEFAULT_CENTRES, session
            ),
            "geolocation_prompt": bool(
                app_settings.setting_or("map.geolocation_prompt", True, session)
            ),
        },
        "qr": {
            "public_base_url": str(
                app_settings.setting_or("qr.public_base_url", "", session) or ""
            ),
            "label_caption": str(app_settings.setting_or("qr.label_caption", "", session) or ""),
        },
        "programme": {
            "current_season": app_settings.setting_or("programme.current_season", None, session),
            "season_label": app_settings.setting_or("programme.season_label", "", session),
        },
        "cache_seconds": CACHE_SECONDS,
    }


# ------------------------------------------------------------------- test buttons


def check_public_url(url: str) -> dict[str, Any]:
    """Does the address a scanned label will open actually answer from outside?"""
    candidate = (url or "").strip()
    if not candidate:
        return {"ok": False, "status": None, "detail": "Give an address to test."}
    if not candidate.startswith(("http://", "https://")):
        return {
            "ok": False,
            "status": None,
            "detail": "The address must start with http:// or https://.",
        }
    warning = None
    if any(host in candidate for host in ("localhost", "127.0.0.1", "0.0.0.0")):
        warning = (
            "This address only works on this computer. A label printed with it cannot be "
            "scanned by a farmer or a buyer."
        )
    reached = _get(candidate)
    return {
        "ok": reached["ok"],
        "status": reached["status"],
        "detail": reached["detail"],
        "warning": warning,
    }


def check_tiles(provider_key: str | None = None, custom_url: str | None = None) -> dict[str, Any]:
    """Fetch one tile, so a provider is proved before every map depends on it."""
    key = (provider_key or "esri_imagery").strip()
    provider = registry.TILE_PROVIDERS.get(key)
    if provider is None:
        return {"ok": False, "status": None, "detail": f"Unknown tile provider {key!r}."}
    template = (custom_url or "").strip() if key == "custom" else str(provider["url"])
    if not template:
        return {"ok": False, "status": None, "detail": "Give the custom tile URL to test."}
    url = (
        template.replace("{z}", str(PROBE_TILE["z"]))
        .replace("{x}", str(PROBE_TILE["x"]))
        .replace("{y}", str(PROBE_TILE["y"]))
        .replace("{s}", "a")
        .replace("{r}", "")
    )
    reached = _get(url)
    return {
        "ok": reached["ok"],
        "status": reached["status"],
        "detail": reached["detail"],
        "url": url,
    }


def _get(url: str) -> dict[str, Any]:
    """One short request. Any failure is reported, never raised: this is a test button."""
    import httpx

    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            response = client.get(url)
    except httpx.TimeoutException:
        return {"ok": False, "status": None, "detail": f"No answer within {int(_TIMEOUT)} seconds."}
    except httpx.HTTPError as exc:
        return {"ok": False, "status": None, "detail": f"Could not be reached: {exc}."}
    ok = response.status_code < 400
    return {
        "ok": ok,
        "status": response.status_code,
        "detail": (
            f"Answered {response.status_code}."
            if ok
            else f"Answered {response.status_code}, which is an error."
        ),
    }


__all__ = ["CACHE_SECONDS", "check_public_url", "check_tiles", "public_config", "tile_layer"]
