from surfy.state import AgentState


def human_gateway_node(state: AgentState) -> dict:
    """사람 개입 게이트웨이 노드.

    - HUMAN executor로 지정된 태스크이거나
    - 모든 retry가 소진되어 사람 개입이 필요한 경우 호출됨
    """
    # TODO: 사용자에게 알림 전송 / 대기 로직
    return {"needs_human_intervention": True}