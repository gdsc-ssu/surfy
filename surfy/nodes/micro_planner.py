from surfy.models.enums import ActionType
from surfy.models.micro import MicroAction, MicroPlan
from surfy.state import AgentState


def capture_screen_node(state: AgentState) -> dict:
    """현재 브라우저 상태를 캡처하는 노드.

    Playwright CDP를 통해 DOM 파싱 + 스크린샷 캡처.
    같은 함수를 capture_screen_pre_micro / capture_screen_pre_review로 등록.
    """
    # TODO: Playwright connect_over_cdp로 브라우저 연결 후
    #   1. page.content()로 HTML 가져와서 BeautifulSoup으로 파싱
    #   2. 인터랙티브 요소에 인덱스 번호 매핑
    #   3. page.screenshot()으로 스크린샷 캡처
    #   4. ScreenState 생성하여 반환
    return {}


def micro_planner_node(state: AgentState) -> dict:
    """미시 계획 노드: 현재 macro task + screen → MicroPlan 생성.

    - 현재 화면(DOM)과 macro task의 description을 분석하여 구체적 액션 리스트 생성
    - 예상치 못한 팝업/오류 감지 시 is_exception=True로 설정
    """
    macro_plan = state.get("macro_plan")
    if macro_plan is None:
        return {"current_micro_plan": MicroPlan(macro_task_id=-1, is_exception=True, exception_reason="No macro plan")}

    current_task = macro_plan.tasks[macro_plan.current_task_index]

    # TODO: LLM 호출로 current_task + current_screen을 분석하여 MicroPlan 생성
    micro_plan = MicroPlan(
        macro_task_id=current_task.task_id,
        actions=[
            MicroAction(
                action_type=ActionType.WAIT,
                description=f"Placeholder for: {current_task.description}",
                expected_outcome=current_task.expected_outcome,
            ),
        ],
        current_action_index=0,
        is_exception=False,
    )

    return {"current_micro_plan": micro_plan}