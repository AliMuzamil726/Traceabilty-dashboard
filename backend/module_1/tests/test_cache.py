"""The 30-second cache and what empties it.

A dashboard figure may be a few seconds old, but it may never be wrong after a write.
These tests pin both halves of that: a repeated read is served from the cache, and any
write anywhere in the product drops it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from module_1.services import cache
from module_1.tests.conftest import cotton_picking


@pytest.fixture(autouse=True)
def _empty_cache() -> Any:
    cache.invalidate()
    yield
    cache.invalidate()


class TestCaching:
    def test_a_repeated_read_is_served_from_the_cache(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)
        admin = as_officer("ADMIN-01")

        first = dashboard("overview", admin, scope="all", crop="cotton")
        again = dashboard("overview", admin, scope="all", crop="cotton")

        assert again["generated_at"] == first["generated_at"]

    def test_each_set_of_parameters_is_cached_on_its_own(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140)
        admin = as_officer("ADMIN-01")

        cotton = dashboard("overview", admin, scope="all", crop="cotton")
        hemp = dashboard("overview", admin, scope="all", crop="hemp")

        # Each crop is answered and cached on its own key: reading cotton again is the
        # cached cotton answer, not the hemp one. (Two fresh reads can land in the same
        # microsecond, so comparing their timestamps is not a reliable signal.)
        assert cache.size() >= 2
        again = dashboard("overview", admin, scope="all", crop="cotton")
        assert again["generated_at"] == cotton["generated_at"]
        assert again["kpis"]["farmers"]["total"] == 1
        assert hemp["kpis"]["farmers"]["total"] == 0

    def test_two_officers_never_share_an_answer(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        make_farm("cotton", sown=140, officer="PK-MUL-01")

        mine = dashboard("overview", as_officer("PK-MUL-01"), scope="mine", crop="cotton")
        theirs = dashboard("overview", as_officer("PK-MUL-02"), scope="mine", crop="cotton")

        assert mine["kpis"]["farmers"]["total"] == 1
        assert theirs["kpis"]["farmers"]["total"] == 0

    def test_each_section_is_cached_separately(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        admin = as_officer("ADMIN-01")
        dashboard("overview", admin, scope="all")
        size_after_one = cache.size()
        dashboard("pipeline", admin, scope="all")

        assert cache.size() > size_after_one


class TestInvalidation:
    def test_registering_a_farmer_drops_the_cache(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        admin = as_officer("ADMIN-01")
        assert dashboard("overview", admin, scope="all")["kpis"]["farmers"]["total"] == 0

        make_farm("cotton")

        assert dashboard("overview", admin, scope="all")["kpis"]["farmers"]["total"] == 1

    def test_mapping_a_field_drops_the_cache(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        from module_1.tests.conftest import REG, square

        farm = make_farm("cotton", field=False)
        admin = as_officer("ADMIN-01")
        assert dashboard("overview", admin, scope="all")["kpis"]["fields"]["total"] == 0

        r = client.post(
            f"{REG}/farmers/{farm['farmer']['id']}/fields",
            json={"geometry": square((29.0, 71.0))},
            headers=farm["headers"],
        )
        assert r.status_code == 201, r.text

        assert dashboard("overview", admin, scope="all")["kpis"]["fields"]["total"] == 1

    def test_a_delivery_drops_the_cache(
        self,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        deliver: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        farm = make_farm("cotton", sown=140, harvest=cotton_picking(ready="yes"))
        admin = as_officer("ADMIN-01")
        before = dashboard("pipeline", admin, scope="all", crop="cotton")
        assert before["stages"][4]["count"] == 0

        deliver(farm, weighbridge=900)

        after = dashboard("pipeline", admin, scope="all", crop="cotton")
        assert after["stages"][4]["count"] == 1

    def test_a_fieldbook_step_save_drops_the_cache(
        self,
        client: Any,
        dashboard: Callable[..., dict[str, Any]],
        make_farm: Callable[..., dict[str, Any]],
        as_officer: Callable[[str], dict[str, str]],
    ) -> None:
        from module_1.tests.conftest import FB, YEAR, cotton_sowing

        farm = make_farm("cotton")  # a field, no fieldbook yet
        admin = as_officer("ADMIN-01")
        before = dashboard("overview", admin, scope="all", crop="cotton")
        assert before["kpis"]["fieldbooks"]["started"] == 0

        opened = client.post(
            f"{FB}/books",
            json={"field_id": farm["field"]["id"], "season_year": YEAR},
            headers=farm["headers"],
        )
        assert opened.status_code in (200, 201), opened.text
        opened = opened.json()
        saved = client.put(
            f"{FB}/books/{opened['id']}/steps/sowing",
            json={"data": cotton_sowing(30)},
            headers=farm["headers"],
        )
        assert saved.status_code == 200, saved.text

        after = dashboard("overview", admin, scope="all", crop="cotton")
        assert after["kpis"]["fieldbooks"]["started"] == 1
        assert after["generated_at"] != before["generated_at"]

    def test_the_subscription_covers_every_event(self) -> None:
        from core.events import KNOWN_EVENTS
        from module_1 import events

        assert set(events.SUBSCRIBES) == set(KNOWN_EVENTS)
        assert events.PUBLISHES == ()

    def test_invalidate_empties_the_store(
        self, dashboard: Callable[..., dict[str, Any]], as_officer: Callable[[str], dict[str, str]]
    ) -> None:
        dashboard("overview", as_officer("ADMIN-01"), scope="all")
        assert cache.size() > 0

        cache.invalidate()

        assert cache.size() == 0
