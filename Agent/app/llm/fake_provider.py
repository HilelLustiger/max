from langchain_core.messages import BaseMessage

from app.llm.contract import LLMResponse


class FakeProvider:
    """Canned-response provider for tests and local dev without an API key."""

    def generate(self, messages: list[BaseMessage], system: str) -> LLMResponse:
        last_user_text = messages[-1].content if messages else ""
        return LLMResponse(
            text=f"fake reply to: {last_user_text}",
            provider="fake",
            model="fake-model",
            input_tokens=1,
            output_tokens=1,
            cache_creation_input_tokens=None,
            cache_read_input_tokens=None,
            finish_reason="stop",
            latency_ms=0,
        )
