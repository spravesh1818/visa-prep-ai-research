"""Normalize LLM response content to plain text.

Gemini 3+ returns ``AIMessage.content`` as a list of blocks such as
``[{"type": "text", "text": "...", "extras": {"signature": "..."}}]``.
Use this helper anywhere text is spoken (TTS), shown in transcripts, or fed
back into prompts — never pass raw ``content`` or ``str(content)`` to TTS.
"""

from __future__ import annotations

from typing import Any


def llm_text(message: Any) -> str:
    """Extract speakable plain text from a LangChain chat response or message."""

    text = getattr(message, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    content = getattr(message, "content", message)
    return content_text(content)


def content_text(content: Any) -> str:
    """Extract plain text from ``AIMessage.content`` (str or provider blocks)."""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                block_text = block.get("text")
                if isinstance(block_text, str) and block_text:
                    parts.append(block_text)
        return " ".join(parts).strip()

    if content is None:
        return ""

    return str(content).strip()
