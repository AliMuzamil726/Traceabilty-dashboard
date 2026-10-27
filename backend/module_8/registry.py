"""Every generic setting in the product, declared in one place.

A "generic" setting is a single value an administrator can change: a flag, a number, a
URL, a small object. It is stored in ``app_settings`` as JSON and read anywhere through
``core.app_settings.get_setting(key)``.

Configuration that belongs to a module's own domain is NOT here. Crop clock days,
delivery tolerances, heap ratios and alert thresholds are rows in the owning module's
table, written only through that module's ``public_api`` (``get_config`` /
``update_config``). Settings calls those functions; it never writes another module's
table (DECISIONS D-117).

Each definition carries its validation, so the API can reject a bad value with a
sentence an officer can act on, and the Settings screen can render the right control
without knowing anything about the key.
"""

from __future__ import annotations

from typing import Any, Final

from core.app_settings import Definition, SettingError

# --------------------------------------------------------------------------- groups

GROUP_MAP: Final = "map"
GROUP_QR: Final = "qr"
GROUP_VALIDATION: Final = "validation"
GROUP_PROGRAMME: Final = "programme"
GROUP_RADAR: Final = "radar"
GROUP_ALERTS: Final = "alerts"

GROUPS: Final[tuple[str, ...]] = (
    GROUP_PROGRAMME,
    GROUP_VALIDATION,
    GROUP_RADAR,
    GROUP_ALERTS,
    GROUP_MAP,
    GROUP_QR,
)

# Tile providers an administrator may choose. Defined in code, not in the database,
# because each one needs a URL template and an attribution its licence requires.
TILE_PROVIDERS: Final[dict[str, dict[str, Any]]] = {
    "esri_imagery": {
        "label": "Esri satellite imagery",
        "url": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ),
        "attribution": (
            "Imagery &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community"
        ),
        "max_zoom": 19,
    },
    "esri_street": {
        "label": "Esri street map",
        "url": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Street_Map/MapServer/tile/{z}/{y}/{x}"
        ),
        "attribution": "Map data &copy; Esri, HERE, Garmin, OpenStreetMap contributors",
        "max_zoom": 19,
    },
    "custom": {
        "label": "Custom XYZ tiles",
        "url": "",  # taken from map.custom_tile_url
        "attribution": "",  # taken from map.custom_attribution
        "max_zoom": 19,
    },
}

LABELS_OVERLAY_URL: Final = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/"
    "World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
)

#: Where each country's map opens when nothing better is known.
DEFAULT_CENTRES: Final[dict[str, dict[str, float]]] = {
    "PK": {"lat": 30.1575, "lng": 71.5249, "zoom": 12},
    "GB": {"lat": 53.2307, "lng": -0.5406, "zoom": 12},
}

#: Label sheet that fits common 3 x 8 A4 stock (the previous hard-coded LabelConfig).
DEFAULT_LABEL_GRID: Final[dict[str, float]] = {
    "columns": 3,
    "rows": 8,
    "margin_top_mm": 13.0,
    "margin_left_mm": 7.0,
    "label_width_mm": 63.5,
    "label_height_mm": 33.9,
    "gap_x_mm": 2.5,
    "gap_y_mm": 0.0,
}


# ----------------------------------------------------------------------- validators


def _centres(value: Any) -> None:
    if not isinstance(value, dict) or not value:
        raise SettingError("Give a centre for at least one country.")
    for country, centre in value.items():
        if not isinstance(country, str) or len(country) != 2:
            raise SettingError("Each key must be a two-letter country code.")
        if not isinstance(centre, dict):
            raise SettingError(f"The centre for {country} must have lat, lng and zoom.")
        try:
            lat = float(centre["lat"])
            lng = float(centre["lng"])
            zoom = int(centre["zoom"])
        except (KeyError, TypeError, ValueError):
            raise SettingError(f"The centre for {country} must have lat, lng and zoom.") from None
        if not -90 <= lat <= 90:
            raise SettingError(f"Latitude for {country} must be between -90 and 90.")
        if not -180 <= lng <= 180:
            raise SettingError(f"Longitude for {country} must be between -180 and 180.")
        if not 1 <= zoom <= 20:
            raise SettingError(f"Zoom for {country} must be between 1 and 20.")


def _label_grid(value: Any) -> None:
    if not isinstance(value, dict):
        raise SettingError("The label grid must be an object.")
    missing = [k for k in DEFAULT_LABEL_GRID if k not in value]
    if missing:
        raise SettingError(f"The label grid is missing: {', '.join(sorted(missing))}.")
    for key in ("columns", "rows"):
        try:
            count = int(value[key])
        except (TypeError, ValueError):
            raise SettingError(f"{key.capitalize()} must be a whole number.") from None
        if not 1 <= count <= 12:
            raise SettingError(f"{key.capitalize()} must be between 1 and 12.")
    for key in DEFAULT_LABEL_GRID:
        if key in ("columns", "rows"):
            continue
        try:
            mm = float(value[key])
        except (TypeError, ValueError):
            raise SettingError(f"{key} must be a number of millimetres.") from None
        if mm < 0 or mm > 300:
            raise SettingError(f"{key} must be between 0 and 300 mm.")
    # A4 is 210 x 297 mm. A grid wider or taller than the page prints nothing usable.
    width = (
        float(value["margin_left_mm"]) * 2
        + int(value["columns"]) * float(value["label_width_mm"])
        + (int(value["columns"]) - 1) * float(value["gap_x_mm"])
    )
    height = (
        float(value["margin_top_mm"]) * 2
        + int(value["rows"]) * float(value["label_height_mm"])
        + (int(value["rows"]) - 1) * float(value["gap_y_mm"])
    )
    if width > 210.5:
        raise SettingError(f"This grid is {width:.0f} mm wide and does not fit A4 (210 mm).")
    if height > 297.5:
        raise SettingError(f"This grid is {height:.0f} mm tall and does not fit A4 (297 mm).")


def _benchmarks(value: Any) -> None:
    if not isinstance(value, dict) or not value:
        raise SettingError("Give a benchmark yield for each crop.")
    for crop, entry in value.items():
        if crop not in ("cotton", "hemp"):
            raise SettingError(f"Unknown crop {crop!r}.")
        if not isinstance(entry, dict) or "kg" not in entry or "unit" not in entry:
            raise SettingError(f"The benchmark for {crop} needs kg and unit.")
        try:
            kg = float(entry["kg"])
        except (TypeError, ValueError):
            raise SettingError(f"The benchmark for {crop} must be a number of kilograms.") from None
        if not 0 < kg <= 100_000:
            raise SettingError(f"The benchmark for {crop} must be above 0 and below 100,000 kg.")
        if entry["unit"] not in ("acre", "ha"):
            raise SettingError(f"The unit for {crop} must be acre or ha.")


def _http_url(value: Any) -> None:
    text = str(value)
    if not text.startswith(("http://", "https://")):
        raise SettingError("The address must start with http:// or https://.")
    if text.endswith("/"):
        raise SettingError("Leave off the trailing slash.")


def _tile_url(value: Any) -> None:
    text = str(value)
    if not text:
        return  # only required when the provider is "custom", checked on save
    _http_url(text.rstrip("/"))
    for token in ("{z}", "{x}", "{y}"):
        if token not in text:
            raise SettingError("A tile address must contain {z}, {x} and {y}.")


# --------------------------------------------------------------------- definitions

DEFINITIONS: Final[tuple[Definition, ...]] = (
    # ------------------------------------------------------------------- programme
    Definition(
        key="programme.current_season",
        group=GROUP_PROGRAMME,
        label="Current season year",
        description=(
            "The season new fieldbooks open in, and the one the dashboard shows by default."
        ),
        type="int",
        default=0,  # 0 means "use the calendar year"
        minimum=0,
        maximum=2100,
        read_by=("Dashboard", "Fieldbook", "Harvest Radar"),
        public=True,
    ),
    Definition(
        key="programme.season_label",
        group=GROUP_PROGRAMME,
        label="Season label",
        description="How a season is written on screen. {year} is replaced by the season year.",
        type="string",
        default="{year}",
        read_by=("Dashboard", "Fieldbook"),
        public=True,
    ),
    # ------------------------------------------------------------------ validation
    Definition(
        key="validation.hemp_id_min_digits",
        group=GROUP_VALIDATION,
        label="Hemp ID number: fewest digits",
        description="A UK grower's identity number must have at least this many digits.",
        type="int",
        default=9,
        minimum=4,
        maximum=20,
        read_by=("Register Farmer",),
    ),
    Definition(
        key="validation.hemp_id_max_digits",
        group=GROUP_VALIDATION,
        label="Hemp ID number: most digits",
        description="A UK grower's identity number may have at most this many digits.",
        type="int",
        default=13,
        minimum=4,
        maximum=20,
        read_by=("Register Farmer",),
    ),
    Definition(
        key="validation.field_min_area_m2",
        group=GROUP_VALIDATION,
        label="Smallest field (m2)",
        description="A mapped boundary smaller than this is rejected as a mis-drawn shape.",
        type="float",
        default=100.0,
        minimum=1.0,
        maximum=100_000.0,
        read_by=("Register Farmer",),
    ),
    Definition(
        key="validation.field_max_area_m2",
        group=GROUP_VALIDATION,
        label="Largest field (m2)",
        description="A boundary larger than this must be mapped as separate fields.",
        type="float",
        default=5_000_000.0,  # 500 hectares
        minimum=1_000.0,
        maximum=100_000_000.0,
        read_by=("Register Farmer",),
    ),
    Definition(
        key="validation.allow_unicode_names",
        group=GROUP_VALIDATION,
        label="Allow names in any script",
        description=(
            "On, a name may be written in Urdu, Arabic or any other script. Off, names "
            "are limited to Latin letters."
        ),
        type="bool",
        default=True,
        read_by=("Register Farmer",),
    ),
    Definition(
        key="validation.postcode_lookup_enabled",
        group=GROUP_VALIDATION,
        label="Look up UK postcodes online",
        description=(
            "On, a UK postcode is looked up at postcodes.io for its county and coordinates. "
            "Off, only the bundled postcode-area table is used."
        ),
        type="bool",
        default=True,
        read_by=("Register Farmer",),
        public=True,
    ),
    # ----------------------------------------------------------------------- radar
    Definition(
        key="radar.benchmark_yields",
        group=GROUP_RADAR,
        label="Benchmark yields",
        description=(
            "Used to estimate a field's quantity before a harvest entry exists. "
            "Cotton in kg per acre, hemp in kg per hectare."
        ),
        type="json",
        default={"cotton": {"kg": 800.0, "unit": "acre"}, "hemp": {"kg": 6000.0, "unit": "ha"}},
        validator=_benchmarks,
        read_by=("Harvest Radar", "Deliveries"),
    ),
    # ---------------------------------------------------------------------- alerts
    Definition(
        key="alerts.ready_without_pickup_days",
        group=GROUP_ALERTS,
        label="Days ready without a pickup request",
        description=(
            "A field ready this long with no pickup request is listed under Needs attention."
        ),
        type="int",
        default=7,
        minimum=1,
        maximum=120,
        read_by=("Dashboard",),
    ),
    Definition(
        key="alerts.heap_idle_days",
        group=GROUP_ALERTS,
        label="Days before a heap counts as idle",
        description="An open heap or batch with nothing added and no bale made for this long.",
        type="int",
        default=14,
        minimum=1,
        maximum=365,
        read_by=("Dashboard",),
    ),
    Definition(
        key="alerts.draft_fieldbook_idle_days",
        group=GROUP_ALERTS,
        label="Days before a draft fieldbook is forgotten",
        description="A draft nobody has touched for this long is listed so it can be finished.",
        type="int",
        default=21,
        minimum=1,
        maximum=365,
        read_by=("Dashboard",),
    ),
    Definition(
        key="alerts.licence_expiry_warning_days",
        group=GROUP_ALERTS,
        label="Days before a hemp licence expires",
        description=(
            "A licence expiring within this many days is flagged; an expired one is critical."
        ),
        type="int",
        default=30,
        minimum=1,
        maximum=365,
        read_by=("Dashboard",),
    ),
    Definition(
        key="alerts.dispatch_grace_days",
        group=GROUP_ALERTS,
        label="Grace days after a scheduled dispatch",
        description=(
            "A scheduled delivery is late this many days after its date without a dispatch."
        ),
        type="int",
        default=0,
        minimum=0,
        maximum=30,
        read_by=("Dashboard",),
    ),
    # ------------------------------------------------------------------------- map
    Definition(
        key="map.tile_provider",
        group=GROUP_MAP,
        label="Map tiles",
        description="The imagery every map in the product draws.",
        type="choice",
        default="esri_imagery",
        choices=tuple(TILE_PROVIDERS),
        read_by=("Register Farmer", "Harvest Radar", "Dashboard", "QR Tracing"),
        public=True,
    ),
    Definition(
        key="map.custom_tile_url",
        group=GROUP_MAP,
        label="Custom tile address",
        description="XYZ template, for example https://tiles.example.com/{z}/{x}/{y}.png",
        type="string",
        default="",
        validator=_tile_url,
        read_by=("Every map",),
        public=True,
    ),
    Definition(
        key="map.custom_attribution",
        group=GROUP_MAP,
        label="Custom tile attribution",
        description="The credit line the tile provider's licence requires. Shown on every map.",
        type="string",
        default="",
        read_by=("Every map",),
        public=True,
    ),
    Definition(
        key="map.labels_overlay",
        group=GROUP_MAP,
        label="Place names over imagery",
        description="Draw road and place names on top of satellite imagery.",
        type="bool",
        default=True,
        read_by=("Every map",),
        public=True,
    ),
    Definition(
        key="map.default_centres",
        group=GROUP_MAP,
        label="Where each country's map opens",
        description="Used when a field has no coordinates yet and the browser gives no location.",
        type="json",
        default=DEFAULT_CENTRES,
        validator=_centres,
        read_by=("Every map",),
        public=True,
    ),
    Definition(
        key="map.geolocation_prompt",
        group=GROUP_MAP,
        label="Ask the browser for the officer's location",
        description="On, the map offers to centre on where the officer is standing.",
        type="bool",
        default=True,
        read_by=("Register Farmer",),
        public=True,
    ),
    # -------------------------------------------------------------------------- qr
    Definition(
        key="qr.public_base_url",
        group=GROUP_QR,
        label="Public address printed on labels",
        description=(
            "Every printed code points at this address. It must be the address a phone "
            "outside the office can open, not localhost."
        ),
        type="string",
        default="http://localhost:5173",
        env_field="public_base_url",
        validator=_http_url,
        read_by=("QR Tracing",),
    ),
    Definition(
        key="qr.label_grid",
        group=GROUP_QR,
        label="Label sheet layout",
        description="Columns, rows, margins and label size in millimetres, for A4 label stock.",
        type="json",
        default=DEFAULT_LABEL_GRID,
        validator=_label_grid,
        read_by=("QR Tracing",),
    ),
    Definition(
        key="qr.label_caption",
        group=GROUP_QR,
        label="Caption under each code",
        description="Printed small under every label. Leave empty for none.",
        type="string",
        default="Scan to trace",
        allow_empty=True,
        read_by=("QR Tracing",),
    ),
)


def by_group() -> dict[str, list[Definition]]:
    """Definitions grouped for the Settings screens, in declaration order."""
    out: dict[str, list[Definition]] = {g: [] for g in GROUPS}
    for definition in DEFINITIONS:
        out.setdefault(definition.group, []).append(definition)
    return out


def install() -> None:
    """Hand the definitions to :mod:`core.app_settings` (called at startup)."""
    from core import app_settings

    app_settings.register(DEFINITIONS)


__all__ = [
    "DEFAULT_CENTRES",
    "DEFAULT_LABEL_GRID",
    "DEFINITIONS",
    "GROUPS",
    "LABELS_OVERLAY_URL",
    "TILE_PROVIDERS",
    "by_group",
    "install",
]
