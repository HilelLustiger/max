from app.config import settings
from app.llm.contract import LLMProvider
from app.llm.langchain_provider import LangChainProvider

_PROVIDERS = {
    "anthropic": lambda: LangChainProvider(
        provider="anthropic", model=settings.llm_model, api_key=settings.anthropic_api_key
    ),
}


def get_provider() -> LLMProvider:
    try:
        build = _PROVIDERS[settings.llm_provider]
    except KeyError:
        raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}") from None
    return build()
