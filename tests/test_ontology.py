"""Ontology loading and validation tests."""

import pytest

from app.ontology import OntologyNotFoundError, available_ontologies, load_ontology


def test_all_ontologies_load():
    catalogue = available_ontologies()
    keys = {o["key"] for o in catalogue}
    assert {"us_f1", "us_j1", "us_b1b2", "us_h1b", "uk_student"} <= keys


def test_load_is_format_tolerant():
    a = load_ontology("US", "F1")
    b = load_ontology("us", "f-1")
    assert a.key == b.key == "us_f1"
    assert a.total_weight() > 0


def test_unknown_ontology_raises():
    with pytest.raises(OntologyNotFoundError):
        load_ontology("Atlantis", "Z9")


def test_topics_have_intents_and_unique_ids():
    o = load_ontology("UK", "Student")
    ids = [t.id for t in o.topics]
    assert len(ids) == len(set(ids))
    assert all(t.intent.strip() for t in o.topics)


def test_ontologies_define_timezone():
    from zoneinfo import ZoneInfo

    uk = load_ontology("UK", "Student")
    us = load_ontology("US", "F1")
    for tz in (uk.timezone, us.timezone):
        assert tz
        ZoneInfo(tz)  # valid IANA
