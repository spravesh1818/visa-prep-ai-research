"""Tests for LLM content normalization (Gemini 3+ block format)."""

from langchain_core.messages import AIMessage

from app.llm.content import content_text, llm_text


def test_content_text_from_plain_string():
    assert content_text("Hello officer.") == "Hello officer."


def test_content_text_from_gemini_blocks():
    blocks = [
        {
            "type": "text",
            "text": "Good morning.",
            "extras": {"signature": "should-not-appear"},
        },
        {
            "type": "text",
            "text": "Please have your documents ready.",
            "extras": {"signature": "also-hidden"},
        },
    ]
    assert (
        content_text(blocks)
        == "Good morning. Please have your documents ready."
    )


def test_llm_text_prefers_message_text_property():
    class _Msg:
        text = "Plain via .text"
        content = [{"type": "text", "text": "ignored"}]

    assert llm_text(_Msg()) == "Plain via .text"


def test_llm_text_from_gemini_message():
    msg = AIMessage(
        content=[
            {
                "type": "text",
                "text": "Hello there.",
                "extras": {"signature": "EpQFCp..."},
            }
        ]
    )
    assert llm_text(msg) == "Hello there."
    assert "signature" not in llm_text(msg)
    assert "type" not in llm_text(msg)
