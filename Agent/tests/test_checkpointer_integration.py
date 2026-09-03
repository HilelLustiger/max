import uuid

import pytest
from app.graph.build import build_graph
from app.graph.checkpointer import build_checkpointer
from app.llm.fake_provider import FakeProvider
from langchain_core.messages import HumanMessage

pytestmark = pytest.mark.integration


@pytest.fixture
def new_thread_id() -> str:
    return str(uuid.uuid4())


def _new_checkpointer_backed_graph(provider):
    """A fresh checkpointer (its own connection pool) + compiled graph, simulating what a
    new process/service instance would build on startup - not chat.py's module-level
    singleton, which stays alive for the whole test run."""
    checkpointer = build_checkpointer()
    graph = build_graph(provider, checkpointer=checkpointer)
    return graph, checkpointer


def _close(checkpointer) -> None:
    checkpointer.conn.close()


def test_conversation_context_survives_a_simulated_restart(new_thread_id):
    config = {"configurable": {"thread_id": new_thread_id}}

    graph_1, checkpointer_1 = _new_checkpointer_backed_graph(FakeProvider())
    try:
        graph_1.invoke({"messages": [HumanMessage(content="my favorite color is blue")]}, config=config)
    finally:
        _close(checkpointer_1)

    provider_2 = FakeProvider()
    graph_2, checkpointer_2 = _new_checkpointer_backed_graph(provider_2)
    try:
        graph_2.invoke({"messages": [HumanMessage(content="what's my favorite color?")]}, config=config)
    finally:
        _close(checkpointer_2)

    # provider_2 never got the first turn's content directly from us - only the checkpointer,
    # loaded fresh by a brand new process/pool, could have supplied it.
    contents = [str(m.content) for m in provider_2.last_messages]
    assert any("blue" in c for c in contents)


def test_a_second_thread_id_does_not_see_the_first_threads_history(new_thread_id):
    other_thread_id = str(uuid.uuid4())

    graph, checkpointer = _new_checkpointer_backed_graph(FakeProvider())
    try:
        graph.invoke(
            {"messages": [HumanMessage(content="secret: the launch code is 4815")]},
            config={"configurable": {"thread_id": new_thread_id}},
        )

        provider_other = FakeProvider()
        graph_other, checkpointer_other = _new_checkpointer_backed_graph(provider_other)
        try:
            graph_other.invoke(
                {"messages": [HumanMessage(content="hi")]},
                config={"configurable": {"thread_id": other_thread_id}},
            )
        finally:
            _close(checkpointer_other)

        contents = [str(m.content) for m in provider_other.last_messages]
        assert not any("4815" in c for c in contents)
    finally:
        _close(checkpointer)


def test_long_conversation_still_produces_a_coherent_bounded_slice_after_truncation(
    new_thread_id, monkeypatch
):
    monkeypatch.setattr("app.graph.build.settings.max_history_tokens", 50)
    config = {"configurable": {"thread_id": new_thread_id}}
    provider = FakeProvider()
    graph, checkpointer = _new_checkpointer_backed_graph(provider)

    try:
        for i in range(20):
            graph.invoke({"messages": [HumanMessage(content=f"message number {i} " * 5)]}, config=config)

        graph.invoke({"messages": [HumanMessage(content="final question")]}, config=config)

        sent = provider.last_messages
        # Far less than the ~41 messages accumulated by then - the budget actually trimmed.
        assert len(sent) < 41
        # The cut respects turn boundaries: starts on a human turn, not a dangling AI/tool message.
        assert isinstance(sent[0], HumanMessage)
        # The in-progress task (the latest question) is never lost to truncation.
        assert sent[-1].content == "final question"
    finally:
        _close(checkpointer)
