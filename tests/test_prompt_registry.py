"""Tests for versioned prompt template loading."""

from __future__ import annotations

import pytest

from app.interview.prompts.loader import PromptLoadError, clear_prompt_cache, load_prompt


@pytest.fixture(autouse=True)
def _clear_caches():
    clear_prompt_cache()
    yield
    clear_prompt_cache()


def test_load_default_greeting():
    tmpl = load_prompt("v1", "openai", "greeting")
    assert "{persona_block}" in tmpl.system
    assert "{local_time}" in tmpl.human
    assert tmpl.variables.get("opener_styles")


def test_google_greeting_override():
    google = load_prompt("v1", "google", "greeting")
    default = load_prompt("v1", "default", "greeting")
    assert google.human != default.human
    assert "plain spoken text" in google.system.lower()


def test_provider_falls_back_to_default_for_question():
    tmpl = load_prompt("v1", "google", "question")
    default = load_prompt("v1", "default", "question")
    assert tmpl.human == default.human


def test_unknown_version_raises():
    with pytest.raises(PromptLoadError, match="Unknown prompt version"):
        load_prompt("v99", "openai", "greeting")
