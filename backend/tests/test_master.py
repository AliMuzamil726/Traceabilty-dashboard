from fastapi.testclient import TestClient


def test_master_keys(client: TestClient) -> None:
    # Keys come back sorted. Derived from the seed file, because every module that is
    # built adds lists of its own.
    from scripts.seed import _load

    expected = sorted({row["list_key"] for row in _load("master_lists.json")})
    assert client.get("/api/v1/master").json() == {"keys": expected}
    assert {"country", "crop", "variety", "tenure", "crop_season", "yes_no"} <= set(expected)


def test_country_list(client: TestClient) -> None:
    body = client.get("/api/v1/master/country").json()
    assert [i["value"] for i in body["items"]] == ["PK", "GB"]
    assert [i["label"] for i in body["items"]] == ["Pakistan", "United Kingdom"]


def test_crop_list_filtered_by_country(client: TestClient) -> None:
    every = client.get("/api/v1/master/crop").json()["items"]
    assert [i["value"] for i in every] == ["cotton", "hemp"]

    pk = client.get("/api/v1/master/crop", params={"country": "pk"}).json()
    assert pk["country"] == "PK"
    assert [i["value"] for i in pk["items"]] == ["cotton"]

    gb = client.get("/api/v1/master/crop", params={"country": "GB"}).json()
    assert [i["value"] for i in gb["items"]] == ["hemp"]


def test_crop_filter_keeps_global_rows(client: TestClient) -> None:
    # Country options carry no crop scope, so a crop filter keeps all of them.
    body = client.get("/api/v1/master/country", params={"crop": "hemp"}).json()
    assert len(body["items"]) == 2


def test_unknown_list_and_bad_key(client: TestClient) -> None:
    r = client.get("/api/v1/master/unknown_list")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "master_list_not_found"
    assert client.get("/api/v1/master/Bad-Key").status_code == 422
    assert client.get("/api/v1/master/crop", params={"country": "PAK"}).status_code == 422
