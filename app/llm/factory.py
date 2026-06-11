"""Central LLM factory.

Every part of the system obtains its chat model through :func:`get_llm`, so the
provider/model can be swapped entirely via environment variables. This makes it
trivial to A/B different LLMs for the interview job.

Supported providers: ``openai``, ``anthropic``, ``google``, ``ollama``.
Optional roles (``interviewer`` / ``evaluator``) allow using a different model
for generation vs. structured evaluation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings, get_settings

LLMRole = Literal["default", "interviewer", "evaluator"]


def _resolve_model_and_temp(
    settings: Settings, role: LLMRole
) -> tuple[str, float]:
    """Pick the model id and temperature for a given role, with fallbacks."""

    model = settings.llm_model
    temperature = settings.llm_temperature

    if role == "interviewer":
        model = settings.interviewer_model or model
        if settings.interviewer_temperature is not None:
            temperature = settings.interviewer_temperature
    elif role == "evaluator":
        model = settings.evaluator_model or model
        if settings.evaluator_temperature is not None:
            temperature = settings.evaluator_temperature

    return model, temperature


def _build_model(
    provider: str, model: str, temperature: float, settings: Settings
) -> BaseChatModel:
    """Instantiate the concrete chat model for ``provider``."""

    max_tokens = settings.llm_max_tokens

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.openai_api_key,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens or 2048,
            api_key=settings.anthropic_api_key,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            max_output_tokens=max_tokens,
            google_api_key=settings.google_api_key,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            temperature=temperature,
            num_predict=max_tokens,
            base_url=settings.ollama_base_url,
        )

    if provider == "deepseek":
        from langchain_deepseek import ChatDeepSeek

        return ChatDeepSeek(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.deepseek_api_key,
        )

    if provider == "moonshot":
        from langchain_moonshot import ChatMoonshot

        return ChatMoonshot(
            model=model,
            temperature=temperature,
            api_key=settings.moonshot_api_key,
            base_url=settings.moonshot_base_url,
        )

    raise ValueError(
        f"Unsupported LLM provider '{provider}'. Expected one of: "
        "openai, anthropic, google, ollama, deepseek, moonshot."
    )


@lru_cache(maxsize=8)
def _cached_llm(provider: str, role: LLMRole) -> BaseChatModel:
    settings = get_settings()
    model, temperature = _resolve_model_and_temp(settings, role)
    return _build_model(provider, model, temperature, settings)


def get_llm(
    role: LLMRole = "default", provider: Optional[str] = None
) -> BaseChatModel:
    """Return a chat model for the given ``role``.

    Parameters
    ----------
    role:
        ``"interviewer"`` for question/probe generation, ``"evaluator"`` for
        structured answer analysis, or ``"default"``.
    provider:
        Override the provider (useful for the model-comparison script). Falls
        back to ``LLM_PROVIDER`` from the environment.
    """

    settings = get_settings()
    resolved_provider = provider or settings.llm_provider
    return _cached_llm(resolved_provider, role)


def get_structured_llm(role: LLMRole, schema):
    """Return an LLM bound to ``schema`` using a provider-appropriate method.

    OpenAI supports strict ``json_schema`` structured outputs; the other
    OpenAI-compatible providers (DeepSeek, Moonshot, etc.) are more reliable with
    tool/``function_calling`` based structured output, which also sidesteps
    strict-schema limitations.
    """

    provider = get_settings().llm_provider
    llm = get_llm(role)
    method = "json_schema" if provider == "openai" else "function_calling"
    return llm.with_structured_output(schema, method=method)


def describe_active_llm() -> dict:
    """Small helper for the ``/config`` endpoint."""

    settings = get_settings()
    interviewer_model, interviewer_temp = _resolve_model_and_temp(
        settings, "interviewer"
    )
    evaluator_model, evaluator_temp = _resolve_model_and_temp(
        settings, "evaluator"
    )
    return {
        "provider": settings.llm_provider,
        "default_model": settings.llm_model,
        "interviewer": {"model": interviewer_model, "temperature": interviewer_temp},
        "evaluator": {"model": evaluator_model, "temperature": evaluator_temp},
    }
