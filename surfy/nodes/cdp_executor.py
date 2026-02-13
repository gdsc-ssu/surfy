from surfy.models.execution import ExecutionResult
from surfy.state import AgentState


def cdp_executor_node(state: AgentState) -> dict:
    """CDP 실행 노드: MicroAction을 하나씩 실행하고 action index를 진행.

    - current_micro_plan의 현재 액션을 실행
    - 실행 후 action_index를 증가시켜 다음 self-loop에서 다음 액션 실행
    - 모든 액션 완료 또는 실패 시 결과 반환
    """
    micro_plan = state.get("current_micro_plan")
    if micro_plan is None:
        result = ExecutionResult(success=False, error_message="No micro plan")
        return {
            "last_execution_result": result,
            "execution_history": [result],
        }

    current_action = micro_plan.actions[micro_plan.current_action_index]

    # TODO: Playwright CDP를 통해 실제 액션 실행
    #   - CLICK: page.click(selector)
    #   - TYPE: page.fill(selector, value)
    #   - SCROLL: page.mouse.wheel(0, delta)
    #   - HOVER: page.hover(selector)
    #   - SELECT_OPTION: page.select_option(selector, value)
    #   - PRESS_KEY: page.keyboard.press(key)
    #   - WAIT: page.wait_for_timeout(ms)
    #   - GO_TO_URL: page.goto(url)
    #   - GO_BACK: page.go_back()

    result = ExecutionResult(
        success=True,
        error_message="",
    )

    next_index = micro_plan.current_action_index + 1
    updated_micro = micro_plan.model_copy(update={"current_action_index": next_index})

    return {
        "current_micro_plan": updated_micro,
        "last_execution_result": result,
        "execution_history": [result],
    }