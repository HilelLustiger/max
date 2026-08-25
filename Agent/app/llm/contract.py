from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import BaseMessage


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


class LLMProvider(Protocol):
    def generate(self, messages: list[BaseMessage], system: str) -> LLMResponse: ...
