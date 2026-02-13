from surfy.models.review import ReviewResult
from surfy.state import AgentState


def reviewer_node(state: AgentState) -> dict:
    """리뷰어 노드: expected outcome vs 현재 화면 비교 → is_success 결정.

    - MacroPlan의 expected_outcome과 실제 화면을 비교
    - 성공/실패만 판단, 다음 행동은 절대 계획하지 않음
    """
    macro_plan = state.get("macro_plan")
    if macro_plan is None:
        result = ReviewResult(
            is_success=False,
            rationale="No macro plan to review against",
        )
        return {"last_review_result": result, "review_history": [result]}

    current_task = macro_plan.tasks[macro_plan.current_task_index]

    # TODO: LLM 호출로 expected_outcome vs current_screen 비교
    result = ReviewResult(
        is_success=True,
        rationale="Placeholder review - always succeeds",
        expected=current_task.expected_outcome,
        observed=state.get("current_screen"),
    )

    return {"last_review_result": result, "review_history": [result]}