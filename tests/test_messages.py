import json
from datetime import datetime

import pytest

from surfy.domain.models.messages import (
    CancelledMessage,
    CancelledMessageData,
    CancelMessage,
    ChatMessage,
    ChatMessageData,
    ConnectedMessage,
    ConnectedMessageData,
    DomHighlightMessage,
    DomHighlightMessageData,
    ErrorMessage,
    ErrorMessageData,
    GetStatusMessage,
    HeartbeatMessage,
    InterruptMessage,
    InterruptMessageData,
    NodeEndMessage,
    NodeEndMessageData,
    NodeStartMessage,
    NodeStartMessageData,
    ResumeMessage,
    ResumeMessageData,
    ResumeValue,
    RunMessage,
    RunMessageData,
    StateUpdateMessage,
    StateUpdateMessageData,
    StepProgressMessage,
    StepProgressMessageData,
    parse_client_message,
)


def test_run_message_roundtrip():
    msg = RunMessage(data=RunMessageData(command="test command", thread_id="thread-123"))
    json_str = msg.model_dump_json()
    parsed = RunMessage.model_validate_json(json_str)
    assert parsed.type == "run"
    assert parsed.data.command == "test command"
    assert parsed.data.thread_id == "thread-123"
    assert isinstance(parsed.timestamp, datetime)


def test_resume_message_roundtrip():
    msg = ResumeMessage(
        data=ResumeMessageData(
            interrupt_type="plan_approval",
            value=ResumeValue(approved=True, modification="looks good"),
        )
    )
    json_str = msg.model_dump_json()
    parsed = ResumeMessage.model_validate_json(json_str)
    assert parsed.type == "resume"
    assert parsed.data.interrupt_type == "plan_approval"
    assert parsed.data.value.approved is True
    assert parsed.data.value.modification == "looks good"


def test_chat_message_roundtrip():
    msg = ChatMessage(data=ChatMessageData(message="hello"))
    json_str = msg.model_dump_json()
    parsed = ChatMessage.model_validate_json(json_str)
    assert parsed.type == "chat"
    assert parsed.data.message == "hello"


def test_cancel_message_roundtrip():
    msg = CancelMessage()
    json_str = msg.model_dump_json()
    parsed = CancelMessage.model_validate_json(json_str)
    assert parsed.type == "cancel"
    assert parsed.data == {}


def test_heartbeat_message_roundtrip():
    msg = HeartbeatMessage()
    json_str = msg.model_dump_json()
    parsed = HeartbeatMessage.model_validate_json(json_str)
    assert parsed.type == "heartbeat"
    assert parsed.data == {}


def test_get_status_message_roundtrip():
    msg = GetStatusMessage()
    json_str = msg.model_dump_json()
    parsed = GetStatusMessage.model_validate_json(json_str)
    assert parsed.type == "get_status"
    assert parsed.data == {}


def test_node_start_message_roundtrip():
    msg = NodeStartMessage(data=NodeStartMessageData(node="planner"))
    json_str = msg.model_dump_json()
    parsed = NodeStartMessage.model_validate_json(json_str)
    assert parsed.type == "node_start"
    assert parsed.data.node == "planner"


def test_node_end_message_roundtrip():
    msg = NodeEndMessage(data=NodeEndMessageData(node="planner", updates={"plan": {"anchor": "test"}}))
    json_str = msg.model_dump_json()
    parsed = NodeEndMessage.model_validate_json(json_str)
    assert parsed.type == "node_end"
    assert parsed.data.node == "planner"
    assert parsed.data.updates["plan"]["anchor"] == "test"


def test_state_update_message_roundtrip():
    msg = StateUpdateMessage(
        data=StateUpdateMessageData(
            plan={"anchor": "test", "tasks": []},
            current_task_idx=1,
            completed_count=1,
            done=False,
            error=None,
        )
    )
    json_str = msg.model_dump_json()
    parsed = StateUpdateMessage.model_validate_json(json_str)
    assert parsed.type == "state_update"
    assert parsed.data.plan is not None
    assert parsed.data.plan["anchor"] == "test"
    assert parsed.data.current_task_idx == 1
    assert parsed.data.completed_count == 1
    assert parsed.data.done is False
    assert parsed.data.error is None


def test_interrupt_message_roundtrip():
    msg = InterruptMessage(data=InterruptMessageData(interrupt_type="plan_approval", payload={"plan": "..."}))
    json_str = msg.model_dump_json()
    parsed = InterruptMessage.model_validate_json(json_str)
    assert parsed.type == "interrupt"
    assert parsed.data.interrupt_type == "plan_approval"
    assert parsed.data.payload["plan"] == "..."


def test_cancelled_message_roundtrip():
    msg = CancelledMessage(data=CancelledMessageData(reason="user requested"))
    json_str = msg.model_dump_json()
    parsed = CancelledMessage.model_validate_json(json_str)
    assert parsed.type == "cancelled"
    assert parsed.data.reason == "user requested"


def test_dom_highlight_message_roundtrip():
    msg = DomHighlightMessage(
        data=DomHighlightMessageData(
            action_type="click",
            target_selector="button#submit",
            bounding_box={"x": 10, "y": 20, "width": 100, "height": 50},
            description="Clicking submit button",
        )
    )
    json_str = msg.model_dump_json()
    parsed = DomHighlightMessage.model_validate_json(json_str)
    assert parsed.type == "dom_highlight"
    assert parsed.data.action_type == "click"
    assert parsed.data.target_selector == "button#submit"
    assert parsed.data.bounding_box is not None
    assert parsed.data.bounding_box["x"] == 10
    assert parsed.data.description == "Clicking submit button"


def test_step_progress_message_roundtrip():
    msg = StepProgressMessage(
        data=StepProgressMessageData(
            node="scout",
            step_number=2,
            description="Navigating to google.com",
            action_type="go_to_url",
        )
    )
    json_str = msg.model_dump_json()
    parsed = StepProgressMessage.model_validate_json(json_str)
    assert parsed.type == "step_progress"
    assert parsed.data.node == "scout"
    assert parsed.data.step_number == 2
    assert parsed.data.description == "Navigating to google.com"
    assert parsed.data.action_type == "go_to_url"


def test_error_message_roundtrip():
    msg = ErrorMessage(data=ErrorMessageData(message="something went wrong", node="actor"))
    json_str = msg.model_dump_json()
    parsed = ErrorMessage.model_validate_json(json_str)
    assert parsed.type == "error"
    assert parsed.data.message == "something went wrong"
    assert parsed.data.node == "actor"


def test_connected_message_roundtrip():
    msg = ConnectedMessage(data=ConnectedMessageData(state={"connected": True}))
    json_str = msg.model_dump_json()
    parsed = ConnectedMessage.model_validate_json(json_str)
    assert parsed.type == "connected"
    assert parsed.data.state is not None
    assert parsed.data.state["connected"] is True


def test_parse_client_message_run():
    raw = json.dumps({"type": "run", "data": {"command": "test", "thread_id": "123"}})
    msg = parse_client_message(raw)
    assert isinstance(msg, RunMessage)
    assert msg.data.command == "test"


def test_parse_client_message_resume():
    raw = json.dumps(
        {
            "type": "resume",
            "data": {
                "interrupt_type": "test",
                "value": {"approved": True, "modification": None},
            },
        }
    )
    msg = parse_client_message(raw)
    assert isinstance(msg, ResumeMessage)
    assert msg.data.value.approved is True


def test_parse_client_message_get_status():
    raw = json.dumps({"type": "get_status", "data": {}})
    msg = parse_client_message(raw)
    assert isinstance(msg, GetStatusMessage)


def test_parse_client_message_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_client_message("invalid json")


def test_parse_client_message_missing_type():
    with pytest.raises(ValueError, match="Message type is missing"):
        parse_client_message(json.dumps({"data": {}}))


def test_parse_client_message_unknown_type():
    with pytest.raises(ValueError, match="Unknown message type: unknown"):
        parse_client_message(json.dumps({"type": "unknown", "data": {}}))
