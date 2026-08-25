from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class UsageCallbackHandler(BaseCallbackHandler):
    def __init__(self) -> None:
        self.input_tokens: int | None = None
        self.output_tokens: int | None = None
        self.cache_creation_input_tokens: int | None = None
        self.cache_read_input_tokens: int | None = None
        self.finish_reason: str | None = None

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        usage = (response.llm_output or {}).get("usage") or (response.llm_output or {}).get(
            "token_usage"
        )
        message = None
        if response.generations:
            message = response.generations[0][0].message
            if not usage:
                usage = getattr(message, "usage_metadata", None)

        if usage:
            self.input_tokens = usage.get("input_tokens")
            self.output_tokens = usage.get("output_tokens")
            self.cache_creation_input_tokens = usage.get("cache_creation_input_tokens")
            self.cache_read_input_tokens = usage.get("cache_read_input_tokens")

        if message is not None:
            self.finish_reason = getattr(message, "response_metadata", {}).get("stop_reason")
