"""Ontology validation helpers."""

from collections.abc import Mapping
from typing import Any


class OntologyValidationError(ValueError):
    """Raised when ontology metadata is structurally invalid."""


REQUIRED_TOP_LEVEL_KEYS = (
    "ontology",
    "objectTypes",
    "linkTypes",
    "functions",
    "actions",
    "roles",
    "permissions",
)


SECTION_NAMES = {
    "objectTypes": "object type",
    "linkTypes": "link type",
    "functions": "function",
    "actions": "action",
    "roles": "role",
}


def _require_mapping(value: object, section: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OntologyValidationError(f"Ontology section '{section}' must be a mapping.")
    return value


def validate_ontology_document(document: object) -> dict[str, Any]:
    """Validate the minimal ontology document structure used by the API."""
    if not isinstance(document, Mapping):
        raise OntologyValidationError("Ontology document root must be a mapping.")

    normalized = dict(document)
    missing = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in normalized]
    if missing:
        raise OntologyValidationError(
            f"Ontology document is missing required top-level keys: {', '.join(missing)}."
        )

    ontology_section = _require_mapping(normalized["ontology"], "ontology")
    for field_name in ("key", "displayName"):
        if field_name not in ontology_section:
            raise OntologyValidationError(
                f"Ontology metadata is missing required field '{field_name}'."
            )

    for section_name, item_label in SECTION_NAMES.items():
        section = _require_mapping(normalized[section_name], section_name)
        for registry_key, definition in section.items():
            definition_mapping = _require_mapping(definition, f"{section_name}.{registry_key}")
            declared_key = definition_mapping.get("key")
            if declared_key is not None and declared_key != registry_key:
                raise OntologyValidationError(
                    f"{item_label.title()} '{registry_key}' declares mismatched key '{declared_key}'."
                )

    _require_mapping(normalized["permissions"], "permissions")
    return normalized
