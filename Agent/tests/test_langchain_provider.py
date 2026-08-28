from unittest.mock import MagicMock

from app.llm.langchain_provider import LangChainProvider
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"sunny in {city}"


def test_generate_without_tools_does_not_bind_tools(monkeypatch):
    provider = LangChainProvider(provider="anthropic", model="fake-model", api_key="test")
    monkeypatch.setattr(
        type(provider._chat_model), "invoke", MagicMock(return_value=AIMessage(content="hi"))
    )
    bind_tools = MagicMock()
    monkeypatch.setattr(type(provider._chat_model), "bind_tools", bind_tools)

    response = provider.generate([HumanMessage(content="hello")], system="sys")

    bind_tools.assert_not_called()
    assert response.text == "hi"
    assert response.tool_calls == []


def test_generate_with_tools_binds_tools_with_cache_control_on_last_one(monkeypatch):
    provider = LangChainProvider(provider="anthropic", model="fake-model", api_key="test")

    fake_tool_calls = [{"name": "get_weather", "args": {"city": "Paris"}, "id": "call_1"}]
    fake_response = AIMessage(content="", tool_calls=fake_tool_calls)
    bound_model = MagicMock()
    bound_model.invoke.return_value = fake_response

    captured_tools = []

    def fake_bind_tools(self, tools, **kwargs):
        captured_tools.append(tools)
        return bound_model

    monkeypatch.setattr(type(provider._chat_model), "bind_tools", fake_bind_tools)

    response = provider.generate(
        [HumanMessage(content="weather?")], system="sys", tools=[get_weather]
    )

    assert len(captured_tools) == 1
    passed_tools = captured_tools[0]
    assert passed_tools[-1]["name"] == "get_weather"
    assert passed_tools[-1]["cache_control"] == {"type": "ephemeral"}
    assert response.tool_calls == fake_response.tool_calls
