"""Object search request schema tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.objects import ObjectSearchRequest


def test_object_search_request_defaults() -> None:
    request = ObjectSearchRequest.model_validate({})

    assert request.query is None
    assert request.filters is None
    assert request.sort is None
    assert request.limit == 20
    assert request.cursor is None


def test_object_search_request_parses_valid_payload() -> None:
    request = ObjectSearchRequest.model_validate(
        {
            "query": "  delayed supplier  ",
            "filters": [
                {
                    "property": "status",
                    "operator": "equals",
                    "value": "delayed",
                }
            ],
            "sort": [
                {
                    "property": "reliabilityScore",
                    "direction": "asc",
                }
            ],
            "limit": 25,
            "cursor": "opaque-token",
        }
    )

    assert request.query == "delayed supplier"
    assert request.filters is not None
    assert request.filters[0].property == "status"
    assert request.sort is not None
    assert request.sort[0].direction == "asc"
    assert request.limit == 25
    assert request.cursor == "opaque-token"


def test_object_search_request_rejects_invalid_sort_direction() -> None:
    with pytest.raises(ValidationError):
        ObjectSearchRequest.model_validate(
            {
                "sort": [
                    {"property": "reliabilityScore", "direction": "up"}
                ]
            }
        )


def test_object_search_request_rejects_invalid_limit() -> None:
    with pytest.raises(ValidationError):
        ObjectSearchRequest.model_validate({"limit": 101})


def test_object_search_request_rejects_malformed_filter_shape() -> None:
    with pytest.raises(ValidationError):
        ObjectSearchRequest.model_validate(
            {"filters": [{"property": "status", "value": "delayed"}]}
        )
