"""Ontology metadata route tests."""

from fastapi.testclient import TestClient


def test_ontology_summary_endpoint_returns_registry_counts(client: TestClient) -> None:
    """Ontology summary should expose registry identity and top-level counts."""
    response = client.get("/api/v1/ontology")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["key"] == "operationalOntology"
    assert payload["displayName"] == "Operational Ontology"
    assert payload["version"] == "1.0.0"
    assert payload["objectTypeCount"] == 16
    assert payload["functionCount"] == 10
    assert payload["actionTypeCount"] == 12
    assert payload["roleCount"] == 5


def test_object_type_collection_endpoint_returns_registered_types(
    client: TestClient,
) -> None:
    """Object-type collection should return deterministic registry items."""
    response = client.get("/api/v1/ontology/object-types")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 16
    assert payload["items"][0]["key"] == "Supplier"


def test_object_type_detail_endpoint_returns_one_definition(client: TestClient) -> None:
    """Object-type detail should return the registry-backed definition."""
    response = client.get("/api/v1/ontology/object-types/Supplier")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["key"] == "Supplier"
    assert payload["primaryKeyProperty"] == "supplierCode"
    assert payload["source"]["table"] == "suppliers"
    assert "supplierToPurchaseOrders" in payload["links"]


def test_object_type_detail_endpoint_returns_structured_not_found(
    client: TestClient,
) -> None:
    """Unknown object types should return the shared structured 404 payload."""
    response = client.get("/api/v1/ontology/object-types/UnknownType")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "OBJECT_NOT_FOUND",
        "message": "Object type 'UnknownType' was not found.",
        "details": {"objectType": "UnknownType"},
    }


def test_other_metadata_collection_endpoints_return_success(client: TestClient) -> None:
    """Link, function, action, and role collections should all be exposed."""
    paths = (
        "/api/v1/ontology/link-types",
        "/api/v1/ontology/functions",
        "/api/v1/ontology/action-types",
        "/api/v1/ontology/roles",
    )

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()["data"]
        assert "items" in payload
        assert "count" in payload
