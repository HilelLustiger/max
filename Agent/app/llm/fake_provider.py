from langchain_core.messages import BaseMessage, ToolMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.tools import BaseTool

from app.llm.contract import LLMResponse


class FakeProvider:
    """Canned-response provider for tests and local dev without an API key.

    Replies with a plain "fake reply to: ..." text by default, even when tools are
    passed in - real conversations shouldn't have tool calls forced onto them just
    because a tool is available. Pass `tool_calls` to script a tool-call round trip:
    each call is popped and returned in order; once a ToolMessage is the latest
    message, it replies using that result instead of requesting another tool call.
    """

    def __init__(self, tool_calls: list[ToolCall] | None = None):
        self._tool_call_queue = list(tool_calls) if tool_calls else []
        self.call_count = 0
        self.last_messages: list[BaseMessage] = []

    def generate(
        self, messages: list[BaseMessage], system: str, tools: list[BaseTool] | None = None
    ) -> LLMResponse:
        self.call_count += 1
        self.last_messages = messages
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

        if tools and self._tool_call_queue:
            tool_call = self._tool_call_queue.pop(0)
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
                tool_calls=[tool_call],
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
