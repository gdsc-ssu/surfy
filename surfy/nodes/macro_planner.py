from surfy.models.enums import ExecutorType, TaskStatus
from surfy.models.macro import MacroPlan, MacroTask
from surfy.state import AgentState


def macro_planner_node(state: AgentState) -> dict:
    """거시 계획 노드: 초기 플랜 생성 / task 진행 / replan 분기.

    - 최초 호출 시: user_command로부터 MacroPlan 생성
    - 이후 호출 시: 현재 task를 EXIT로 마킹하고 다음 task로 진행
    - replan 필요 시: review 실패로 재진입했을 때 플랜 수정
    """
    macro_plan = state.get("macro_plan")
    last_review = state.get("last_review_result")

    # --- 최초 호출: 플랜이 없으면 새로 생성 ---
    if macro_plan is None:
        # TODO: LLM 호출로 user_command를 분석하여 MacroPlan 생성
        new_plan = MacroPlan(
            anchor=state["user_command"],
            tasks=[
                MacroTask(
                    task_id=0,
                    description=f"Execute: {state['user_command']}",
                    executor=ExecutorType.AGENT,
                    expected_outcome="Task completed successfully",
                    status=TaskStatus.RUNNING,
                ),
            ],
            current_task_index=0,
        )
        return {"macro_plan": new_plan, "micro_retry_count": 0}

    # --- 이전 task 성공 → 다음 task로 진행 ---
    tasks = list(macro_plan.tasks)
    current_idx = macro_plan.current_task_index

    if last_review and last_review.is_success:
        tasks[current_idx] = tasks[current_idx].model_copy(
            update={"status": TaskStatus.EXIT}
        )
        next_idx = current_idx + 1

        if next_idx >= len(tasks):
            updated_plan = macro_plan.model_copy(
                update={"tasks": tasks, "current_task_index": next_idx}
            )
            return {"macro_plan": updated_plan, "is_complete": True}

        tasks[next_idx] = tasks[next_idx].model_copy(
            update={"status": TaskStatus.RUNNING}
        )
        updated_plan = macro_plan.model_copy(
            update={"tasks": tasks, "current_task_index": next_idx}
        )
        return {
            "macro_plan": updated_plan,
            "current_micro_plan": None,
            "micro_retry_count": 0,
        }

    # --- Replan: review 실패로 재진입 ---
    # TODO: LLM 호출로 실패 원인을 분석하여 플랜 재수립
    updated_plan = macro_plan.model_copy(
        update={"replan_count": macro_plan.replan_count + 1}
    )
    return {
        "macro_plan": updated_plan,
        "macro_retry_count": state.get("macro_retry_count", 0) + 1,
        "current_micro_plan": None,
        "micro_retry_count": 0,
    }