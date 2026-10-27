"""One accessor for every generic setting: database override, then ``.env``, then default.

A module that needs a configurable number calls :func:`get_setting("map.tile_provider")`
and never reads the table or the environment itself. The value is resolved in this
order:

1. a row in ``app_settings`` written by an administrator in Settings (Module 8);
2. the matching field on :class:`core.config.Settings` (that is, ``backend/.env``),
   when the definition names one;
3. the default declared in the registry.

Definitions live in ``module_8/registry.py`` and are handed to this module at startup
(``app.registry``), the same way event handlers and guards are registered, because
``core`` must not import a module. Until they are registered, :func:`get_setting`
still answers from ``.env`` and defaults, so the app boots and the tests of other
modules need no Settings fixture.

Caching: resolved values are kept in a process-wide dictionary and cleared whenever
``config.changed`` is published (Module 8 publishes it after every write) or the
registry is replaced. One process and one worker is the deployment for this phase; a
multi-worker deployment replaces :func:`clear_cache` with a shared invalidation.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models.app_setting import AppSetting

logger = logging.getLogger("sawie.settings")

#: Value types a setting may declare. ``json`` covers small objects such as a map
#: centre or a label grid; everything else is a scalar the UI can render as one field.
TYPES = ("string", "int", "float", "bool", "choice", "json")


class SettingError(ValueError):
    """A value that does not satisfy its definition."""


@dataclass(frozen=True)
class Definition:
    """One generic setting, declared in code."""

    key: str
    group: str
    label: str
    description: str
    type: str
    default: Any
    #: Field on :class:`core.config.Settings` consulted before the default.
    env_field: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    pattern: str | None = None
    choices: tuple[Any, ...] | None = None
    #: Never returned by the public config endpoint and masked in the API.
    sensitive: bool = False
    #: A change only takes effect after a restart (shown as a warning in the UI).
    needs_restart: bool = False
    #: Plain-English list of who reads it, for the Settings screen.
    read_by: tuple[str, ...] = ()
    #: Exposed by ``GET /api/v1/settings/public`` to the browser.
    public: bool = False
    #: An empty string is a meaningful value (an optional caption, a custom URL).
    allow_empty: bool = False
    #: Extra check that raises :class:`SettingError`, for shapes a range cannot express.
    validator: Callable[[Any], None] | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.type not in TYPES:  # pragma: no cover - a typo in the registry
            raise ValueError(f"{self.key}: unknown type {self.type!r}")

    def coerce(self, value: Any) -> Any:
        """Convert an incoming value to this setting's type, or raise."""
        try:
            if self.type == "int":
                if isinstance(value, bool) or (isinstance(value, float) and value != int(value)):
                    raise ValueError
                return int(value)
            if self.type == "float":
                if isinstance(value, bool):
                    raise ValueError
                return float(value)
            if self.type == "bool":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str) and value.strip().lower() in (
                    "true",
                    "false",
                    "1",
                    "0",
                    "yes",
                    "no",
                ):
                    return value.strip().lower() in ("true", "1", "yes")
                raise ValueError
            if self.type in ("string", "choice"):
                if not isinstance(value, str | int | float) or isinstance(value, bool):
                    raise ValueError
                return str(value).strip()
            return value  # json: any shape, checked by the validator
        except (TypeError, ValueError):
            raise SettingError(f"{self.label} must be a {self.type}.") from None

    def validate(self, value: Any) -> Any:
        """Coerce and check one value, returning what should be stored."""
        value = self.coerce(value)
        if self.choices is not None and value not in self.choices:
            allowed = ", ".join(str(c) for c in self.choices)
            raise SettingError(f"{self.label} must be one of: {allowed}.")
        if self.minimum is not None and isinstance(value, int | float) and value < self.minimum:
            raise SettingError(f"{self.label} cannot be below {_plain(self.minimum)}.")
        if self.maximum is not None and isinstance(value, int | float) and value > self.maximum:
            raise SettingError(f"{self.label} cannot be above {_plain(self.maximum)}.")
        if self.pattern is not None and isinstance(value, str):
            import re

            if not re.match(self.pattern, value):
                raise SettingError(f"{self.label} is not in the expected format.")
        if (
            self.type == "string"
            and not self.choices
            and value == ""
            and self.default != ""
            and not self.allow_empty
        ):
            raise SettingError(f"{self.label} cannot be empty.")
        if self.validator is not None:
            self.validator(value)
        return value


def _plain(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)


class _Registry:
    """The declared settings plus the resolved-value cache, guarded by one lock."""

    def __init__(self) -> None:
        self._definitions: dict[str, Definition] = {}
        self._cache: dict[str, Any] = {}
        self._lock = threading.RLock()

    def replace(self, definitions: Iterable[Definition]) -> None:
        with self._lock:
            self._definitions = {d.key: d for d in definitions}
            self._cache.clear()

    def clear(self) -> None:
        with self._lock:
            self._definitions = {}
            self._cache.clear()

    def clear_cache(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._cache.clear()
            else:
                self._cache.pop(key, None)

    @property
    def definitions(self) -> dict[str, Definition]:
        with self._lock:
            return dict(self._definitions)

    def get_cached(self, key: str) -> tuple[bool, Any]:
        with self._lock:
            if key in self._cache:
                return True, self._cache[key]
            return False, None

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = value


_REGISTRY = _Registry()


def register(definitions: Iterable[Definition]) -> None:
    """Install the declared settings (called once at startup by ``app.registry``)."""
    _REGISTRY.replace(definitions)


def clear_registry() -> None:
    """Forget the definitions and the cache (startup and tests)."""
    _REGISTRY.clear()


def clear_cache(key: str | None = None) -> None:
    """Drop resolved values, so the next read sees a new override."""
    _REGISTRY.clear_cache(key)


def definitions() -> dict[str, Definition]:
    return _REGISTRY.definitions


def get_definition(key: str) -> Definition:
    try:
        return _REGISTRY.definitions[key]
    except KeyError:
        raise SettingError(f"Unknown setting {key!r}.") from None


def is_registered() -> bool:
    return bool(_REGISTRY.definitions)


def get_setting(key: str, session: Session | None = None, *, settings: Any | None = None) -> Any:
    """The value in force for ``key``: override, then ``.env``, then default.

    ``session`` is optional so a caller that has one avoids opening a second; without
    it the override is read on a short-lived session from the process database. A
    resolved value is cached until ``config.changed`` clears it.
    """
    definition = _REGISTRY.definitions.get(key)
    if definition is None:
        raise SettingError(f"Unknown setting {key!r}.")

    hit, cached = _REGISTRY.get_cached(key)
    if hit:
        return cached

    value = _resolve(definition, session, settings)
    _REGISTRY.put(key, value)
    return value


def _resolve(definition: Definition, session: Session | None, settings: Any | None) -> Any:
    stored = _stored_value(definition.key, session)
    if stored is not None:
        try:
            return definition.validate(stored)
        except SettingError:
            logger.warning(
                "Stored value for %s is no longer valid; falling back to the default.",
                definition.key,
            )
    if definition.env_field:
        env_value = _env_value(definition, settings)
        if env_value is not None:
            return env_value
    return definition.default


def _stored_value(key: str, session: Session | None) -> Any:
    if session is not None:
        return _select(session, key)
    from core.database import get_process_database

    database = get_process_database()
    if database is None:
        return None
    with database.session_factory() as fresh:
        return _select(fresh, key)


def _select(session: Session, key: str) -> Any:
    try:
        return (
            session.execute(select(AppSetting.value).where(AppSetting.key == key)).scalars().first()
        )
    except Exception:  # noqa: BLE001 - before create_all the table is absent; no value yet
        logger.debug("app_settings is not readable yet for %s", key)
        return None


def _env_value(definition: Definition, settings: Any | None) -> Any:
    if settings is None:
        from core.config import get_settings

        settings = get_settings()
    raw = getattr(settings, definition.env_field or "", None)
    if raw is None or raw == "":
        return None
    try:
        return definition.validate(raw)
    except SettingError:  # pragma: no cover - a bad .env value
        logger.warning("Value of %s in .env is not valid; using the default.", definition.env_field)
        return None


def setting_or(key: str, fallback: Any, session: Session | None = None) -> Any:
    """The configured value, or ``fallback`` when the registry is not installed.

    Used by module helpers that must keep working in a unit test that never starts the
    app (and therefore never registered the definitions). The fallback is always the
    constant the module used before it became configurable, so behaviour is identical.
    """
    try:
        return get_setting(key, session)
    except SettingError:
        return fallback


def resolve_all(session: Session | None = None, *, public_only: bool = False) -> dict[str, Any]:
    """Every setting in force, for the public config endpoint and system information."""
    out: dict[str, Any] = {}
    for key, definition in _REGISTRY.definitions.items():
        if public_only and (not definition.public or definition.sensitive):
            continue
        out[key] = get_setting(key, session)
    return out


def sources(session: Session, keys: Sequence[str] | None = None) -> dict[str, str]:
    """Where each value came from: ``database``, ``env`` or ``default``."""
    wanted = keys or list(_REGISTRY.definitions)
    stored = {
        row.key: row
        for row in session.execute(select(AppSetting).where(AppSetting.key.in_(wanted))).scalars()
    }
    out: dict[str, str] = {}
    for key in wanted:
        definition = _REGISTRY.definitions.get(key)
        if definition is None:
            continue
        if key in stored:
            out[key] = "database"
        elif definition.env_field and _env_value(definition, None) is not None:
            out[key] = "env"
        else:
            out[key] = "default"
    return out


__all__ = [
    "TYPES",
    "Definition",
    "SettingError",
    "clear_cache",
    "clear_registry",
    "definitions",
    "get_definition",
    "get_setting",
    "is_registered",
    "register",
    "resolve_all",
    "setting_or",
    "sources",
]
