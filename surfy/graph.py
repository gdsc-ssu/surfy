import logging
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from surfy.domain.models import ActionType, ActorOutput, EvalResult, HistoryEntry, RouteMap, Task
from surfy.domain.services import ActorService, EvaluatorService, PlannerService, ScoutService
from surfy.state import AgentState

logger = logging.getLogger(__name__)


def _current_task(state: AgentState) -> Task | None:
    plan = state["plan"]
    if plan is None:
        return None
    if state["current_task_idx"] >= len(plan.tasks):
        return None
    return plan.tasks[state["current_task_idx"]]


def compile_graph(
    scout: ScoutService,
    planner: PlannerService,
    actor: ActorService,
    evaluator: EvaluatorService,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    async def scout_node(state: AgentState) -> dict[str, object]:
        try:
            route_map: RouteMap = await scout.scout(state["command"])
            return {"route_map": route_map}
        except Exception as e:
            logger.warning("Scout failed: %s. Falling back to blind planning.", e)
            return {"route_map": None}

    async def planner_node(state: AgentState) -> dict[str, object]:
        plan = state["plan"]
        if plan is None:
            new_plan = await planner.create_plan(state["command"], route_map=state["route_map"])
            if not new_plan.tasks:
                return {"plan": new_plan, "done": True, "retry_count": 0, "current_task_idx": 0, "eval_result": None}
            return {"plan": new_plan, "current_task_idx": 0, "retry_count": 0, "eval_result": None, "error": None}

        eval_result = state["eval_result"]
        if eval_result is not None and not eval_result.success:
            failed_task = _current_task(state)
            if failed_task is None:
                return {"done": True, "error": eval_result.reason}
            replanned = await planner.replan(plan, failed_task, eval_result.reason)
            if not replanned.tasks:
                return {"plan": replanned, "done": True, "retry_count": 0, "current_task_idx": 0, "eval_result": None}
            return {"plan": replanned, "current_task_idx": 0, "retry_count": 0, "eval_result": None, "error": None}

        if state["current_task_idx"] >= len(plan.tasks):
            next_plan = await planner.next_tasks(plan, state["completed_tasks"])
            if not next_plan.tasks:
                return {"plan": next_plan, "done": True, "retry_count": 0, "eval_result": None}
            return {"plan": next_plan, "current_task_idx": 0, "retry_count": 0, "eval_result": None, "error": None}

        return {}

    async def actor_node(state: AgentState) -> dict[str, object]:
        task = _current_task(state)
        if task is None:
            return {"done": True}

        result = await actor.execute_task(task)
        action_type = ActionType.DONE if result.success else ActionType.STUCK
        summary_action = ActorOutput(thinking=task.description, action_type=action_type, value=result.message)
        history_entry = HistoryEntry(action=summary_action, result=result, step=None)

        return {
            "history": [history_entry],
            "last_page_state": result.page_state,
            "error": None if result.success else result.message,
        }

    async def evaluator_node(state: AgentState) -> dict[str, object]:
        task = _current_task(state)
        if task is None:
            return {"done": True}

        page_state = state["last_page_state"]
        if page_state is None:
            eval_result = EvalResult(success=False, reason="페이지 상태가 없어 평가할 수 없습니다.")
        else:
            eval_result = await evaluator.evaluate(task, page_state)

        if eval_result.success:
            return {
                "eval_result": eval_result,
                "completed_tasks": [task],
                "current_task_idx": state["current_task_idx"] + 1,
                "retry_count": 0,
                "error": None,
            }
        return {
            "eval_result": eval_result,
            "retry_count": state["retry_count"] + 1,
            "error": eval_result.reason,
        }

    def human_gateway_node(state: AgentState) -> dict[str, object]:
        _ = state
        user_input = input("재시도 한도를 초과했습니다. 종료하려면 'exit', 계속하려면 Enter: ").strip()
        if user_input.lower() == "exit":
            return {"done": True}
        return {"retry_count": 0}

    def route_after_planner(state: AgentState) -> Literal["actor", "END"]:
        if state["done"]:
            return "END"
        task = _current_task(state)
        if task is None:
            return "END"
        return "actor"

    def route_after_evaluator(state: AgentState) -> Literal["planner", "actor", "human_gateway", "END"]:
        if state["done"]:
            return "END"

        eval_result = state["eval_result"]
        if eval_result is None:
            return "END"

        if eval_result.success:
            task = _current_task(state)
            if task is not None:
                return "actor"
            return "planner"

        if state["retry_count"] <= state["max_retries"]:
            return "planner"
        return "human_gateway"

    def route_after_human(state: AgentState) -> Literal["planner", "END"]:
        if state["done"]:
            return "END"
        return "planner"

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("scout", scout_node)
    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node("actor", actor_node)
    graph_builder.add_node("evaluator", evaluator_node)
    graph_builder.add_node("human_gateway", human_gateway_node)

    graph_builder.set_entry_point("scout")

    graph_builder.add_edge("scout", "planner")

    graph_builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "actor": "actor",
            "END": END,
        },
    )
    graph_builder.add_edge("actor", "evaluator")
    graph_builder.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {
            "planner": "planner",
            "actor": "actor",
            "human_gateway": "human_gateway",
            "END": END,
        },
    )
    graph_builder.add_conditional_edges(
        "human_gateway",
        route_after_human,
        {
            "planner": "planner",
            "END": END,
        },
    )

    return graph_builder.compile(checkpointer=checkpointer)
