from app.graph.build import build_graph
from app.llm.fake_provider import FakeProvider
from langchain_core.messages import HumanMessage


def test_graph_invokes_provider_and_returns_reply():
    graph = build_graph(FakeProvider())
    result = graph.invoke({"messages": [HumanMessage(content="hello")]})
    reply = result["messages"][-1]
    assert reply.content == "fake reply to: hello"
    assert reply.response_metadata["provider"] == "fake"
