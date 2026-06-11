"""Ontology layer: structured visa-interview knowledge loaded from YAML."""

from app.ontology.loader import (
    OntologyNotFoundError,
    available_ontologies,
    load_ontology,
)
from app.ontology.models import (
    ConsistencyRule,
    OfficerPersona,
    Ontology,
    Topic,
)

__all__ = [
    "ConsistencyRule",
    "OfficerPersona",
    "Ontology",
    "OntologyNotFoundError",
    "Topic",
    "available_ontologies",
    "load_ontology",
]
