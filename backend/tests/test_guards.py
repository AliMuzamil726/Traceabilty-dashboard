import pytest

from core.errors import ConflictError
from core.guards import FIELD_CAN_DELETE, FIELD_CAN_EDIT_GEOMETRY, GuardRegistry, GuardResult


def test_no_checks_means_allowed() -> None:
    registry = GuardRegistry()
    outcome = registry.check(FIELD_CAN_DELETE, field_id="F1")
    assert outcome.allowed
    registry.enforce(FIELD_CAN_DELETE, field_id="F1")


def test_denials_are_collected_and_enforced() -> None:
    registry = GuardRegistry()
    registry.register(
        FIELD_CAN_DELETE,
        lambda field_id: GuardResult.deny(
            "field_has_fieldbook", "Field has a fieldbook.", field_id=field_id
        ),
        owner="module_3",
    )
    registry.register(FIELD_CAN_DELETE, lambda field_id: GuardResult.allow(), owner="module_4")
    registry.register(
        FIELD_CAN_DELETE,
        lambda field_id: GuardResult.deny("field_has_delivery", "Field has a delivery."),
        owner="module_5",
    )
    outcome = registry.check(FIELD_CAN_DELETE, field_id="F1")
    assert not outcome.allowed
    assert [d.code for d in outcome.denials] == ["field_has_fieldbook", "field_has_delivery"]
    assert registry.registered(FIELD_CAN_DELETE) == ["module_3", "module_4", "module_5"]

    with pytest.raises(ConflictError) as info:
        registry.enforce(FIELD_CAN_DELETE, field_id="F1")
    assert info.value.code == "field_has_fieldbook"
    assert info.value.details["guard"] == FIELD_CAN_DELETE
    assert len(info.value.details["reasons"]) == 2
    assert info.value.details["reasons"][0]["field_id"] == "F1"


def test_guards_are_independent_by_name() -> None:
    registry = GuardRegistry()
    registry.register(
        FIELD_CAN_EDIT_GEOMETRY, lambda **_: GuardResult.deny("locked", "Locked."), owner="m3"
    )
    assert registry.check(FIELD_CAN_DELETE).allowed
    assert not registry.check(FIELD_CAN_EDIT_GEOMETRY).allowed
    registry.clear()
    assert registry.check(FIELD_CAN_EDIT_GEOMETRY).allowed
