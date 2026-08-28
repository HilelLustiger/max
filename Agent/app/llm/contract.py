from dataclasses import dataclass, field
from typing import Protocol

from langchain_core.messages import BaseMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.tools import BaseTool


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    cache_creation_input_tokens: int | None
    cache_read_input_tokens: int | None
    finish_reason: str | None
    latency_ms: int
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(Protocol):
    def generate(
        self, messages: list[BaseMessage], system: str, tools: list[BaseTool] | None = None
    ) -> LLMResponse: ...
