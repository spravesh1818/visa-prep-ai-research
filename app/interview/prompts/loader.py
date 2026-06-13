"""Load and cache versioned prompt YAML templates."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

PROMPTS_ROOT = Path(__file__).parent
PROMPT_KINDS = (
    "greeting",
    "question",
    "probe",
    "closing",
    "evaluation",
    "report_narrative",
)


class PromptTemplate(BaseModel):
    """A single prompt kind (system + human templates)."""

    system: str
    human: str
    variables: dict[str, Any] = Field(default_factory=dict)


class SharedFragments(BaseModel):
    """Cross-prompt fragments loaded from shared.yaml."""

    anti_script_rules: str = ""


class PromptLoadError(LookupError):
    """Raised when a prompt template cannot be resolved."""


def _version_dir(version: str) -> Path:
    path = PROMPTS_ROOT / version
    if not path.is_dir():
        raise PromptLoadError(
            f"Unknown prompt version '{version}'. "
            f"Expected directory: {path}. Available: {_available_versions()}"
        )
    return path


def _available_versions() -> list[str]:
    return sorted(
        p.name
        for p in PROMPTS_ROOT.iterdir()
        if p.is_dir() and not p.name.startswith("_") and p.name != "__pycache__"
    )


@lru_cache(maxsize=32)
def load_shared(version: str, provider: str) -> SharedFragments:
    """Load shared fragments; provider dir may override anti_script_rules."""

    base_path = _version_dir(version) / "default" / "shared.yaml"
    if not base_path.is_file():
        raise PromptLoadError(f"Missing shared prompts: {base_path}")

    with base_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    provider_path = _version_dir(version) / provider / "shared.yaml"
    if provider_path.is_file():
        with provider_path.open(encoding="utf-8") as fh:
            override = yaml.safe_load(fh) or {}
        raw = {**raw, **override}

    return SharedFragments.model_validate(raw)


@lru_cache(maxsize=128)
def load_prompt(version: str, provider: str, kind: str) -> PromptTemplate:
    """Resolve a prompt kind: provider-specific YAML, else default."""

    if kind not in PROMPT_KINDS:
        raise PromptLoadError(
            f"Unknown prompt kind '{kind}'. Expected one of: {', '.join(PROMPT_KINDS)}"
        )

    tried: list[str] = []
    for candidate in (provider, "default"):
        path = _version_dir(version) / candidate / f"{kind}.yaml"
        tried.append(str(path))
        if path.is_file():
            with path.open(encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
            return PromptTemplate.model_validate(raw)

    raise PromptLoadError(
        f"No prompt template for version='{version}', provider='{provider}', "
        f"kind='{kind}'. Tried:\n  " + "\n  ".join(tried)
    )


def clear_prompt_cache() -> None:
    """Clear cached templates (useful in tests)."""

    load_shared.cache_clear()
    load_prompt.cache_clear()
