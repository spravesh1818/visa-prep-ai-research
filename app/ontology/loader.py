"""Load and cache ontology YAML files into validated Pydantic models."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.ontology.models import Ontology

DATA_DIR = Path(__file__).parent / "data"


class OntologyNotFoundError(LookupError):
    """Raised when no ontology matches the requested country + visa type."""


def _normalize(value: str) -> str:
    return value.strip().lower().replace("-", "").replace("/", "").replace(" ", "")


@lru_cache(maxsize=1)
def _load_all() -> dict[str, Ontology]:
    """Parse every ``*.yaml`` in the data directory into an Ontology."""

    registry: dict[str, Ontology] = {}
    for path in sorted(DATA_DIR.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        ontology = Ontology.model_validate(raw)
        registry[ontology.key] = ontology
    return registry


def available_ontologies() -> list[dict[str, str]]:
    """Return a catalogue of supported country + visa-type combinations."""

    return [
        {
            "key": o.key,
            "country": o.country,
            "visa_type": o.visa_type,
            "display_name": o.display_name,
        }
        for o in _load_all().values()
    ]


def load_ontology(country: str, visa_type: str) -> Ontology:
    """Look up an ontology by country + visa type (tolerant of formatting)."""

    registry = _load_all()
    target = f"{_normalize(country)}_{_normalize(visa_type)}"

    for key, ontology in registry.items():
        normalized_key = f"{_normalize(ontology.country)}_{_normalize(ontology.visa_type)}"
        if normalized_key == target:
            return ontology

    raise OntologyNotFoundError(
        f"No ontology for country='{country}', visa_type='{visa_type}'. "
        f"Available: {[o['key'] for o in available_ontologies()]}"
    )
