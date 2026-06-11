"""University credibility service tests."""

from app.knowledge import assess_university


def test_top_tier_increases_score():
    m = assess_university("MIT")
    assert m.tier == "top"
    assert m.score_adjustment > 0


def test_fuzzy_typo_matches_low_tier():
    m = assess_university("silcon valley univercity")
    assert m.matched_name == "Silicon Valley University"
    assert m.tier == "low"
    assert m.score_adjustment < 0


def test_diploma_mill_is_strong_negative():
    m = assess_university("University of Farmington")
    assert m.tier == "diploma_mill"
    assert m.score_adjustment <= -0.5


def test_unknown_university():
    m = assess_university("Completely Made Up Institute of Nowhere")
    assert m.tier == "unknown"
    assert m.matched_name is None


def test_empty_name():
    m = assess_university("")
    assert m.tier == "unknown"


def test_accredited_but_unranked_is_recognized():
    # The school from the bulk registry that prompted this feature.
    m = assess_university("University of Colorado at Colorado Springs")
    assert m.matched_name is not None
    assert m.tier == "recognized"
    assert m.score_adjustment == 0.0


def test_no_subset_false_positives():
    # "University of Washington" must not collapse into "University of Mary Washington".
    uw = assess_university("University of Washington")
    assert uw.matched_name == "University of Washington"
    assert uw.tier == "high"

    mary = assess_university("University of Mary Washington")
    assert "Mary" in (mary.matched_name or "")


def test_curated_tier_survives_bulk_import():
    # Georgia Tech keeps its curated 'high' tier despite IPEDS '-Main Campus' name.
    for name in ["Georgia Tech", "Georgia Institute of Technology"]:
        assert assess_university(name).tier == "high"
