from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.tools import BaseTool

from app.llm.contract import LLMResponse


class FakeProvider:
    """Canned-response provider for tests and local dev without an API key.

    Simulates a tool-call round trip: given tools and no prior tool result, it
    requests the first tool; once a ToolMessage is the latest message, it replies
    using that result instead of requesting the tool again.
    """

    def generate(
        self, messages: list[BaseMessage], system: str, tools: list[BaseTool] | None = None
    ) -> LLMResponse:
        last_message = messages[-1] if messages else None

        if isinstance(last_message, ToolMessage):
            return LLMResponse(
                text=f"fake reply using tool result: {last_message.content}",
                provider="fake",
                model="fake-model",
                input_tokens=1,
                output_tokens=1,
                cache_creation_input_tokens=None,
                cache_read_input_tokens=None,
                finish_reason="stop",
                latency_ms=0,
            )

        if tools:
            tool = tools[0]
            return LLMResponse(
                text="",
                provider="fake",
                model="fake-model",
                input_tokens=1,
                output_tokens=1,
                cache_creation_input_tokens=None,
                cache_read_input_tokens=None,
                finish_reason="tool_calls",
                latency_ms=0,
                tool_calls=[{"name": tool.name, "args": {}, "id": "fake-call-1"}],
            )

        last_user_text = last_message.content if last_message else ""
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
