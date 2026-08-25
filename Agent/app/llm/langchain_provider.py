import time

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, SystemMessage

from app.llm.contract import LLMResponse
from app.metrics.usage_callback import UsageCallbackHandler


class LangChainProvider:
    def __init__(self, provider: str, model: str, api_key: str) -> None:
        self._provider = provider
        self._model = model
        self._chat_model = ChatAnthropic(model=model, api_key=api_key)

    def generate(self, messages: list[BaseMessage], system: str) -> LLMResponse:
        callback = UsageCallbackHandler()
        start = time.monotonic()
        result = self._chat_model.invoke(
            [SystemMessage(content=system), *messages], config={"callbacks": [callback]}
        )
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
        )
