"""Reading and writing the generic settings, with history and optimistic concurrency.

Every write here does the same four things, in this order: validate against the
registry definition, write the override, record the old and new value in the history
and the audit log, then publish ``config.changed`` so caches (``core.app_settings``,
Module 4's dataset cache, the dashboard's) drop what they hold.

Concurrency: the client sends the ``version`` it loaded. If the stored row has moved
on, the save is refused with the current value rather than quietly overwriting another
administrator's change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from core import app_settings, audit
from core.app_settings import Definition, SettingError
from core.deps import CurrentOfficer
from core.errors import AppError, NotFoundError, ValidationAppError
from core.events import CONFIG_CHANGED, bus
from module_8.repository import AppSettingRepository, SettingHistoryRepository

#: Entity name used in the audit log for a generic setting.
AUDIT_ENTITY = "app_setting"


class StaleVersionError(AppError):
    """Someone else saved this setting since it was loaded."""

    status_code = 409
    code = "stale_version"


@dataclass(frozen=True)
class SettingView:
    """One setting as the Settings screen needs it."""

    key: str
    group: str
    label: str
    description: str
    type: str
    value: Any
    default: Any
    source: str
    version: int
    minimum: float | None
    maximum: float | None
    pattern: str | None
    choices: tuple[Any, ...] | None
    sensitive: bool
    public: bool
    needs_restart: bool
    read_by: tuple[str, ...]
    is_default: bool
    changed_by: str | None
    changed_at: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "group": self.group,
            "label": self.label,
            "description": self.description,
            "type": self.type,
            "value": self.value,
            "default": self.default,
            "source": self.source,
            "version": self.version,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "pattern": self.pattern,
            "choices": list(self.choices) if self.choices else None,
            "sensitive": self.sensitive,
            "public": self.public,
            "needs_restart": self.needs_restart,
            "read_by": list(self.read_by),
            "is_default": self.is_default,
            "changed_by": self.changed_by,
            "changed_at": self.changed_at,
        }


class SettingsValueService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.values = AppSettingRepository(session)
        self.history = SettingHistoryRepository(session)

    # ------------------------------------------------------------------- reading

    def definition(self, key: str) -> Definition:
        try:
            return app_settings.get_definition(key)
        except SettingError:
            raise NotFoundError(
                f"There is no setting called {key}.", code="unknown_setting"
            ) from None

    def list_all(self, group: str | None = None) -> list[SettingView]:
        definitions = app_settings.definitions()
        keys = [k for k, d in definitions.items() if group is None or d.group == group]
        stored = self.values.all_by_key(keys)
        sources = app_settings.sources(self.session, keys)
        latest = self.history.latest_for_keys(keys)
        out: list[SettingView] = []
        for key in keys:
            definition = definitions[key]
            row = stored.get(key)
            entry = latest.get(key)
            value = app_settings.get_setting(key, self.session)
            out.append(
                SettingView(
                    key=key,
                    group=definition.group,
                    label=definition.label,
                    description=definition.description,
                    type=definition.type,
                    value="(hidden)" if definition.sensitive else value,
                    default=definition.default,
                    source=sources.get(key, "default"),
                    version=row.version if row else 0,
                    minimum=definition.minimum,
                    maximum=definition.maximum,
                    pattern=definition.pattern,
                    choices=definition.choices,
                    sensitive=definition.sensitive,
                    public=definition.public,
                    needs_restart=definition.needs_restart,
                    read_by=definition.read_by,
                    is_default=value == definition.default,
                    changed_by=entry.changed_by if entry else None,
                    changed_at=entry.changed_at.isoformat() if entry else None,
                )
            )
        return out

    def get(self, key: str) -> SettingView:
        self.definition(key)
        for view in self.list_all():
            if view.key == key:
                return view
        raise NotFoundError(f"There is no setting called {key}.", code="unknown_setting")

    # ------------------------------------------------------------------- writing

    def set(
        self,
        key: str,
        value: Any,
        officer: CurrentOfficer,
        *,
        expected_version: int | None = None,
        reason: str | None = None,
    ) -> SettingView:
        definition = self.definition(key)
        try:
            cleaned = definition.validate(value)
        except SettingError as error:
            raise ValidationAppError(
                str(error), code="invalid_setting", details={"key": key}
            ) from None

        self._check_cross_field(key, cleaned)

        row = self.values.get_by_key(key)
        current_version = row.version if row else 0
        if expected_version is not None and expected_version != current_version:
            raise StaleVersionError(
                "This setting was changed by someone else while you were editing it. "
                "Reload to see the current value.",
                details={"key": key, "current_version": current_version},
            )

        before = app_settings.get_setting(key, self.session)
        if before == cleaned and row is not None:
            return self.get(key)

        self.values.upsert(key, cleaned, officer.id)
        self.history.record(
            key=key, old_value=before, new_value=cleaned, officer_id=officer.id, reason=reason
        )
        audit.record(
            AUDIT_ENTITY,
            key,
            audit.ACTION_UPDATE,
            officer.id,
            audit.compute_diff(
                {"value": "(hidden)" if definition.sensitive else before},
                {"value": "(hidden)" if definition.sensitive else cleaned},
            ),
            session=self.session,
        )
        self._publish(key, definition.group)
        self.session.commit()
        app_settings.clear_cache()
        return self.get(key)

    def reset(self, key: str, officer: CurrentOfficer) -> SettingView:
        """Drop the override so the value falls back to ``.env`` or the default."""
        definition = self.definition(key)
        before = app_settings.get_setting(key, self.session)
        self.values.remove(key)
        app_settings.clear_cache()
        after = app_settings.get_setting(key, self.session)
        self.history.record(
            key=key,
            old_value=before,
            new_value=after,
            officer_id=officer.id,
            reason="Reset to default",
        )
        audit.record(
            AUDIT_ENTITY,
            key,
            audit.ACTION_UPDATE,
            officer.id,
            audit.compute_diff({"value": before}, {"value": after}),
            session=self.session,
        )
        self._publish(key, definition.group)
        self.session.commit()
        app_settings.clear_cache()
        return self.get(key)

    def restore(self, history_id: str, officer: CurrentOfficer) -> SettingView:
        """Put back the value a history entry replaced."""
        entry = self.history.get(history_id)
        if entry is None:
            raise NotFoundError("That change is not in the history.", code="history_not_found")
        return self.set(
            entry.key,
            entry.old_value,
            officer,
            reason=f"Restored the value from {entry.changed_at:%d %b %Y %H:%M} UTC",
        )

    def history_for(self, key: str | None, limit: int = 50) -> list[dict[str, Any]]:
        if key:
            self.definition(key)
        return [
            {
                "id": e.id,
                "key": e.key,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "changed_by": e.changed_by,
                "changed_at": e.changed_at.isoformat(),
                "reason": e.reason,
            }
            for e in self.history.list_for(key, limit=limit)
        ]

    # -------------------------------------------------------------------- helpers

    def _check_cross_field(self, key: str, value: Any) -> None:
        """Rules that need a second setting to decide."""
        if key == "validation.hemp_id_min_digits":
            other = app_settings.get_setting("validation.hemp_id_max_digits", self.session)
            if value > other:
                raise ValidationAppError(
                    "The fewest digits cannot be more than the most digits.",
                    code="invalid_setting",
                )
        if key == "validation.hemp_id_max_digits":
            other = app_settings.get_setting("validation.hemp_id_min_digits", self.session)
            if value < other:
                raise ValidationAppError(
                    "The most digits cannot be fewer than the fewest digits.",
                    code="invalid_setting",
                )
        if key == "validation.field_min_area_m2":
            other = app_settings.get_setting("validation.field_max_area_m2", self.session)
            if value >= other:
                raise ValidationAppError(
                    "The smallest field must be smaller than the largest field.",
                    code="invalid_setting",
                )
        if key == "validation.field_max_area_m2":
            other = app_settings.get_setting("validation.field_min_area_m2", self.session)
            if value <= other:
                raise ValidationAppError(
                    "The largest field must be larger than the smallest field.",
                    code="invalid_setting",
                )
        if key == "map.tile_provider" and value == "custom":
            url = app_settings.get_setting("map.custom_tile_url", self.session)
            if not url:
                raise ValidationAppError(
                    "Give the custom tile address before choosing custom tiles.",
                    code="invalid_setting",
                )
            if not app_settings.get_setting("map.custom_attribution", self.session):
                raise ValidationAppError(
                    "Custom tiles need the attribution their licence requires.",
                    code="invalid_setting",
                )

    def _publish(self, key: str, group: str) -> None:
        bus.publish(
            CONFIG_CHANGED,
            {"key": key, "group": group},
            session=self.session,
        )


__all__ = ["AUDIT_ENTITY", "SettingView", "SettingsValueService", "StaleVersionError"]
