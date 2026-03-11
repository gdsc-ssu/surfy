from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt


class SimpleState(TypedDict):
    input: str
    output: str
    interrupted: bool


def first_node(state: SimpleState):
    return {"input": state["input"] + " -> first"}


def interrupt_node(state: SimpleState):
    # interrupt returns the value passed to Command(resume=...)
    answer = interrupt({"question": "continue?", "data": state["input"]})
    return {"output": f"received: {answer}", "interrupted": True}


def create_test_graph():
    workflow = StateGraph(SimpleState)
    workflow.add_node("first", first_node)
    workflow.add_node("interrupt_node", interrupt_node)

    workflow.set_entry_point("first")
    workflow.add_edge("first", "interrupt_node")
    workflow.add_edge("interrupt_node", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


@pytest.mark.asyncio
async def test_interrupt_pauses_graph():
    graph = create_test_graph()
    config = {"configurable": {"thread_id": "test_1"}}
    initial_state = {"input": "hello", "output": "", "interrupted": False}

    # Run until interrupt
    steps = []
    async for step in graph.astream(initial_state, config, stream_mode="updates"):
        steps.append(step)

    # Verify it stopped at interrupt_node
    # The last step should be 'first' node update, then it hits interrupt in 'interrupt_node'
    assert len(steps) > 0
    assert "first" in steps[0]

    # Check state - it should be suspended at interrupt_node
    state = await graph.aget_state(config)
    assert state.next == ("interrupt_node",)


@pytest.mark.asyncio
async def test_interrupt_payload_received():
    graph = create_test_graph()
    config = {"configurable": {"thread_id": "test_2"}}
    initial_state = {"input": "payload_test", "output": "", "interrupted": False}

    # Run until interrupt
    async for _ in graph.astream(initial_state, config):
        pass

    state = await graph.aget_state(config)
    # In langgraph, tasks contain information about interrupts
    assert len(state.tasks) > 0
    interrupts = state.tasks[0].interrupts
    assert len(interrupts) > 0
    assert interrupts[0].value["question"] == "continue?"
    assert interrupts[0].value["data"] == "payload_test -> first"


@pytest.mark.asyncio
async def test_resume_continues_graph():
    graph = create_test_graph()
    config = {"configurable": {"thread_id": "test_3"}}
    initial_state = {"input": "resume_test", "output": "", "interrupted": False}

    # 1. Run until interrupt
    async for _ in graph.astream(initial_state, config):
        pass

    # 2. Resume with Command
    resume_value = "yes_please"
    steps_after_resume = []
    async for step in graph.astream(Command(resume=resume_value), config, stream_mode="updates"):
        steps_after_resume.append(step)

    # 3. Verify completion
    assert len(steps_after_resume) > 0
    assert "interrupt_node" in steps_after_resume[0]

    final_state = await graph.aget_state(config)
    assert final_state.values["output"] == f"received: {resume_value}"
    assert final_state.values["interrupted"] is True
    assert final_state.next == ()
