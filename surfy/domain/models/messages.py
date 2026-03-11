from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class BaseMessage(BaseModel):
    """WebSocket 메시지 기본 모델."""

    type: str
    """메시지 타입."""

    timestamp: datetime = Field(default_factory=datetime.now)
    """메시지 생성 시각."""


# --- Client to Server Messages ---


class RunMessageData(BaseModel):
    command: str
    thread_id: str | None = None


class RunMessage(BaseMessage):
    """에이전트 실행 요청 메시지."""

    type: Literal["run"] = "run"
    data: RunMessageData


class ResumeValue(BaseModel):
    approved: bool
    modification: str | None = None


class ResumeMessageData(BaseModel):
    interrupt_type: str
    value: ResumeValue


class ResumeMessage(BaseMessage):
    """중단된 프로세스 재개 메시지."""

    type: Literal["resume"] = "resume"
    data: ResumeMessageData


class ChatMessageData(BaseModel):
    message: str


class ChatMessage(BaseMessage):
    """채팅 메시지."""

    type: Literal["chat"] = "chat"
    data: ChatMessageData


class CancelMessage(BaseMessage):
    """실행 취소 메시지."""

    type: Literal["cancel"] = "cancel"
    data: dict[str, Any] = Field(default_factory=dict)


class HeartbeatMessage(BaseMessage):
    """하트비트 메시지."""

    type: Literal["heartbeat"] = "heartbeat"
    data: dict[str, Any] = Field(default_factory=dict)


class GetStatusMessage(BaseMessage):
    """현재 상태 요청 메시지."""

    type: Literal["get_status"] = "get_status"
    data: dict[str, Any] = Field(default_factory=dict)


# --- Server to Client Messages ---


class NodeStartMessageData(BaseModel):
    node: str


class NodeStartMessage(BaseMessage):
    """그래프 노드 시작 알림."""

    type: Literal["node_start"] = "node_start"
    data: NodeStartMessageData


class NodeEndMessageData(BaseModel):
    node: str
    updates: dict[str, Any]


class NodeEndMessage(BaseMessage):
    """그래프 노드 종료 알림."""

    type: Literal["node_end"] = "node_end"
    data: NodeEndMessageData


class StateUpdateMessageData(BaseModel):
    plan: dict[str, Any] | None = None
    current_task_idx: int
    completed_count: int
    done: bool
    error: str | None = None


class StateUpdateMessage(BaseMessage):
    """에이전트 상태 업데이트 알림."""

    type: Literal["state_update"] = "state_update"
    data: StateUpdateMessageData


class InterruptMessageData(BaseModel):
    interrupt_type: Literal["plan_approval", "human_gateway", "completion_check"]
    payload: dict[str, Any]


class InterruptMessage(BaseMessage):
    """사용자 개입 요청 알림."""

    type: Literal["interrupt"] = "interrupt"
    data: InterruptMessageData


class CancelledMessageData(BaseModel):
    reason: str


class CancelledMessage(BaseMessage):
    """실행 취소 완료 알림."""

    type: Literal["cancelled"] = "cancelled"
    data: CancelledMessageData


class DomHighlightMessageData(BaseModel):
    action_type: str
    target_selector: str | None = None
    bounding_box: dict[str, float] | None = None
    description: str | None = None


class DomHighlightMessage(BaseMessage):
    """DOM 하이라이트 요청 알림."""

    type: Literal["dom_highlight"] = "dom_highlight"
    data: DomHighlightMessageData


class ErrorMessageData(BaseModel):
    message: str
    node: str | None = None


class ErrorMessage(BaseMessage):
    """에러 발생 알림."""

    type: Literal["error"] = "error"
    data: ErrorMessageData


class ConnectedMessageData(BaseModel):
    state: dict[str, Any] | None = None
    running: bool = False


class ConnectedMessage(BaseMessage):
    """연결 성공 알림."""

    type: Literal["connected"] = "connected"
    data: ConnectedMessageData


ClientMessage = RunMessage | ResumeMessage | ChatMessage | CancelMessage | HeartbeatMessage | GetStatusMessage


def parse_client_message(raw: str) -> ClientMessage:
    """JSON 문자열을 클라이언트 메시지 객체로 파싱한다.

    Args:
        raw: JSON 문자열.

    Returns:
        파싱된 메시지 객체.

    Raises:
        ValueError: 알 수 없는 메시지 타입이거나 파싱 실패 시.
    """
    import json

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    msg_type = data.get("type")
    if not msg_type:
        raise ValueError("Message type is missing")

    match msg_type:
        case "run":
            return RunMessage.model_validate(data)
        case "resume":
            return ResumeMessage.model_validate(data)
        case "chat":
            return ChatMessage.model_validate(data)
        case "cancel":
            return CancelMessage.model_validate(data)
        case "heartbeat":
            return HeartbeatMessage.model_validate(data)
        case "get_status":
            return GetStatusMessage.model_validate(data)
        case _:
            raise ValueError(f"Unknown message type: {msg_type}")
