from langgraph.graph import END, START, StateGraph

from surfy.models.enums import ExecutorType
from surfy.nodes.cdp_executor import cdp_executor_node
from surfy.nodes.human_gateway import human_gateway_node
from surfy.nodes.macro_planner import macro_planner_node
from surfy.nodes.micro_planner import capture_screen_node, micro_planner_node
from surfy.nodes.reviewer import reviewer_node
from surfy.state import AgentState


# ── Routing 함수 (순수 함수: state만 읽어서 다음 노드 결정) ──


def route_after_macro(state: AgentState) -> str:
    if state.get("is_complete"):
        return END

    macro_plan = state.get("macro_plan")
    if macro_plan is None:
        return END

    current_task = macro_plan.tasks[macro_plan.current_task_index]
    if current_task.executor == ExecutorType.HUMAN:
        return "human_gateway"

    return "capture_screen_pre_micro" # TODO: DOM 트리 파싱하는 걸로 바뀔 수 있음


def route_after_micro(state: AgentState) -> str:
    micro_plan = state.get("current_micro_plan")
    if micro_plan and micro_plan.is_exception:
        return "macro_planner"
    return "cdp_executor"


def route_after_executor(state: AgentState) -> str:
    """매 액션 실행 후 항상 review로 보낸다."""
    return "capture_screen_pre_review"


def route_after_review(state: AgentState) -> str:
    review = state.get("last_review_result")
    if review is None:
        return "macro_planner"

    if review.is_success:
        # 남은 micro action이 있으면 다음 액션 실행
        micro_plan = state.get("current_micro_plan")
        if micro_plan and micro_plan.current_action_index < len(micro_plan.actions):
            return "cdp_executor"
        # 모든 micro action 완료 → 다음 macro task
        return "macro_planner"

    # FAILURE 처리
    micro_retries = state.get("micro_retry_count", 0)
    max_micro = state.get("max_micro_retries", 3)
    macro_retries = state.get("macro_retry_count", 0)
    max_macro = state.get("max_macro_retries", 2)

    if micro_retries < max_micro:
        return "micro_planner"

    if macro_retries < max_macro:
        return "macro_planner"

    return "human_gateway"


# ── 그래프 구성 ──


def compile_graph():
    graph = StateGraph(AgentState)

    # 노드 등록
    graph.add_node("macro_planner", macro_planner_node)
    graph.add_node("capture_screen_pre_micro", capture_screen_node)
    graph.add_node("micro_planner", micro_planner_node)
    graph.add_node("cdp_executor", cdp_executor_node)
    graph.add_node("capture_screen_pre_review", capture_screen_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("human_gateway", human_gateway_node)

    # 엣지 연결
    graph.add_edge(START, "macro_planner")
    graph.add_conditional_edges("macro_planner", route_after_macro)
    graph.add_edge("capture_screen_pre_micro", "micro_planner")
    graph.add_conditional_edges("micro_planner", route_after_micro)
    graph.add_conditional_edges("cdp_executor", route_after_executor)
    graph.add_edge("capture_screen_pre_review", "reviewer")
    graph.add_conditional_edges("reviewer", route_after_review)
    graph.add_edge("human_gateway", END) # TODO: 이게 맞나?


    return graph.compile()