"""Greeting/closing prompts must vary so the officer never sounds scripted."""

from app.interview.prompts import closing_messages, greeting_messages
from app.ontology import load_ontology


def _human(messages):
    return messages[-1].content


def test_greeting_prompt_varies_across_calls():
    ontology = load_ontology("US", "F1")
    seen = {
        _human(greeting_messages(ontology.officer_persona, ontology.display_name, None))
        for _ in range(20)
    }
    # The injected style + nonce should yield many distinct prompts.
    assert len(seen) > 1


def test_closing_prompt_varies_and_hides_decision():
    ontology = load_ontology("US", "F1")
    seen = {
        _human(closing_messages(ontology.officer_persona, ontology.display_name, []))
        for _ in range(20)
    }
    assert len(seen) > 1
    # Closing instructions must forbid leaking the decision.
    sample = closing_messages(ontology.officer_persona, ontology.display_name, [])
    system_text = sample[0].content.lower()
    assert "decision" in system_text
