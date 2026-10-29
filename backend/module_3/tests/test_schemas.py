"""The form definitions load, are well formed, and reference only real master lists."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient

from module_3.services import formschema as fs

COTTON_STEPS = [
    "field_info",
    "land_preparation",
    "sowing",
    "nutrient_management",
    "irrigation",
    "weed_management",
    "pest_disease",
    "energy",
    "labour_social",
    "harvest",
    "transport",
]
HEMP_STEPS = [
    "field_info",
    "land_preparation",
    "sowing",
    "nutrient_management",
    "crop_monitoring",
    "weeds_pests",
    "harvest",
    "retting",
    "baling",
]


@pytest.mark.parametrize(("crop", "keys"), [("cotton", COTTON_STEPS), ("hemp", HEMP_STEPS)])
def test_each_crop_has_its_steps_in_order(crop: str, keys: list[str]) -> None:
    definition = fs.load_definition(crop)
    assert [s["key"] for s in definition["steps"]] == keys
    assert [s["order"] for s in definition["steps"]] == list(range(1, len(keys) + 1))
    assert definition["version"]


def test_cotton_has_11_steps_and_hemp_has_9() -> None:
    assert len(fs.load_definition("cotton")["steps"]) == 11
    assert len(fs.load_definition("hemp")["steps"]) == 9


@pytest.mark.parametrize("crop", ["cotton", "hemp"])
def test_every_field_has_the_keys_the_renderer_needs(crop: str) -> None:
    for step in fs.load_definition(crop)["steps"]:
        for key in ("key", "title", "order", "repeatable", "required", "fields"):
            assert key in step, (step["key"], key)
        for f in step["fields"]:
            assert f["key"]
            assert f["label"]
            assert f["type"] in fs.FIELD_TYPES
            if f["type"] in ("select", "multiselect", "yesno"):
                assert f["list_key"]


@pytest.mark.parametrize("crop", ["cotton", "hemp"])
def test_every_list_key_exists_in_the_master_lists(client: TestClient, crop: str) -> None:
    definition = fs.load_definition(crop)
    for list_key in fs.list_keys(definition):
        r = client.get(
            f"/api/v1/master/{list_key}", params={"country": definition["country"], "crop": crop}
        )
        assert r.status_code == 200, list_key
        assert r.json()["items"], f"{list_key} has no options for {crop}"


@pytest.mark.parametrize("crop", ["cotton", "hemp"])
def test_condition_and_warning_values_exist_in_their_lists(client: TestClient, crop: str) -> None:
    """A visible_if or warn_values naming a value that is not in the list would never fire."""
    definition = fs.load_definition(crop)
    for step in definition["steps"]:
        by_key = {f["key"]: f for f in step["fields"]}
        for f in step["fields"]:
            checks: list[tuple[str, list[str]]] = []
            cond = f.get("visible_if")
            if cond:
                target = by_key[cond["field"]]
                checks.append((target["list_key"], cond.get("in", []) + cond.get("not_in", [])))
            if f.get("warn_values"):
                checks.append((f["list_key"], f["warn_values"]))
            for list_key, values in checks:
                items = client.get(
                    f"/api/v1/master/{list_key}",
                    params={"country": definition["country"], "crop": crop},
                ).json()["items"]
                allowed = {i["value"] for i in items}
                assert set(values) <= allowed, (step["key"], f["key"], set(values) - allowed)


@pytest.mark.parametrize("crop", ["cotton", "hemp"])
def test_suggestion_maps_name_real_products(client: TestClient, crop: str) -> None:
    definition = fs.load_definition(crop)
    for step in definition["steps"]:
        for field_key, mapping in step.get("suggestions", {}).items():
            list_key = next(f["list_key"] for f in step["fields"] if f["key"] == field_key)
            items = client.get(
                f"/api/v1/master/{list_key}",
                params={"country": definition["country"], "crop": crop},
            ).json()["items"]
            assert set(mapping) <= {i["value"] for i in items}


def test_the_schema_endpoint_serves_the_file_unchanged(client: TestClient) -> None:
    body = client.get("/api/v1/fieldbook/schemas/cotton").json()
    assert body == fs.load_definition("cotton")
    assert client.get("/api/v1/fieldbook/schemas/wheat").status_code == 404


def test_the_last_steps_follow_the_season() -> None:
    cotton = fs.load_definition("cotton")["steps"]
    assert [s["key"] for s in cotton[-3:]] == ["labour_social", "harvest", "transport"]
    assert fs.load_definition("hemp")["steps"][-1]["key"] == "baling"


def _broken(mutate: Any) -> dict[str, Any]:
    doc = copy.deepcopy(fs.load_definition("cotton"))
    mutate(doc)
    return doc


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("version"),
        lambda d: d["steps"][0]["fields"][0].update(type="slider"),
        lambda d: d["steps"][0]["fields"][0].pop("list_key"),
        lambda d: d["steps"][1].update(key="field_info"),
        lambda d: d["steps"][0].update(order=7),
        lambda d: d["steps"][1]["rules"][0].update(kind="mystery"),
        lambda d: d["steps"][1]["rules"][0].update(level="loud"),
        lambda d: d["steps"][1]["fields"][6]["visible_if"].update(field="nope"),
        lambda d: d["pickup"].update(step="nope"),
    ],
)
def test_the_loader_rejects_malformed_definitions(mutate: Any) -> None:
    with pytest.raises(fs.SchemaDefinitionError):
        fs._check_definition(_broken(mutate))
