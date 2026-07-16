"""Ontology YAML loading logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.ontology.registry import OntologyRegistry
from app.ontology.validator import validate_ontology_document


ONTOLOGY_PATH = Path(__file__).with_name("ontology.yaml")


def load_ontology_document(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the raw ontology YAML document."""
    ontology_path = path or ONTOLOGY_PATH
    document = yaml.safe_load(ontology_path.read_text(encoding="utf-8"))
    return validate_ontology_document(document)


def load_ontology_registry(path: Path | None = None) -> OntologyRegistry:
    """Load the ontology registry from the configured YAML document."""
    return OntologyRegistry.from_document(load_ontology_document(path))
