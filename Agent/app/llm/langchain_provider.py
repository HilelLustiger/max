import logging
import time

from langchain_anthropic import ChatAnthropic, convert_to_anthropic_tool
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.tools import BaseTool

from app.llm.contract import LLMResponse
from app.metrics.usage_callback import UsageCallbackHandler

logger = logging.getLogger(__name__)


class LangChainProvider:
    def __init__(self, provider: str, model: str, api_key: str) -> None:
        self._provider = provider
        self._model = model
        self._chat_model = ChatAnthropic(model=model, api_key=api_key)

    def generate(
        self, messages: list[BaseMessage], system: str, tools: list[BaseTool] | None = None
    ) -> LLMResponse:
        chat_model = self._chat_model
        if tools:
            # Tool schemas are static across calls, so mark them cacheable: cache_control
            # on the last tool schema caches everything up to and including it.
            anthropic_tools = [convert_to_anthropic_tool(tool) for tool in tools]
            anthropic_tools[-1] = {**anthropic_tools[-1], "cache_control": {"type": "ephemeral"}}
            chat_model = chat_model.bind_tools(anthropic_tools)

        # The system prompt is identical across calls within a conversation (only the date
        # segment changes, at most once a day), so it's cacheable the same way tool schemas are.
        system_message = SystemMessage(
            content=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        )

        callback = UsageCallbackHandler()
        start = time.monotonic()
        try:
            result = chat_model.invoke([system_message, *messages], config={"callbacks": [callback]})
        except Exception:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "provider_call_failed",
                extra={
                    "event": "provider_call_failed",
                    "provider": self._provider,
                    "model": self._model,
                    "latency_ms": elapsed_ms,
                },
            )
            raise
        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            text=result.content,
            provider=self._provider,
            model=self._model,
            input_tokens=callback.input_tokens,
            output_tokens=callback.output_tokens,
            cache_creation_input_tokens=callback.cache_creation_input_tokens,
            cache_read_input_tokens=callback.cache_read_input_tokens,
            finish_reason=callback.finish_reason,
            latency_ms=latency_ms,
            tool_calls=result.tool_calls,
        )
