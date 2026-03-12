import logging
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from surfy.domain.models import ActionType, ActorOutput, EvalResult, HistoryEntry, RouteMap, Task
from surfy.domain.models.research import ResearchResult
from surfy.domain.services import ActorService, EvaluatorService, PlannerService, ResearcherService, ScoutService
from surfy.state import AgentState

logger = logging.getLogger(__name__)
MAX_COMPLETED_TASKS = 8


def _current_task(state: AgentState) -> Task | None:
    plan = state["plan"]
    if plan is None:
        return None
    if state["current_task_idx"] >= len(plan.tasks):
        return None
    return plan.tasks[state["current_task_idx"]]


def _is_repeated_plan(next_tasks: list[Task], completed_tasks: list[Task]) -> bool:
    if not next_tasks or not completed_tasks:
        return False
    completed_descriptions = {task.description.strip() for task in completed_tasks}
    return all(task.description.strip() in completed_descriptions for task in next_tasks)


def _is_simple_navigation_command(command: str) -> bool:
    normalized = command.strip()
    if "http://" in normalized or "https://" in normalized:
        return True
    return len(normalized) < 10


def compile_graph(
    scout: ScoutService,
    planner: PlannerService,
    actor: ActorService,
    evaluator: EvaluatorService,
    researcher: ResearcherService | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    scout_max_steps: int = 20,
) -> CompiledStateGraph:
    async def research_node(state: AgentState) -> dict[str, object]:
        if _is_simple_navigation_command(state["command"]):
            return {"research_result": None}
        if researcher is None:
            return {"research_result": None}
        try:
            result: ResearchResult = await researcher.research(state["command"])
            return {"research_result": result}
        except Exception as e:
            logger.warning("Research failed: %s. Skipping.", e)
            return {"research_result": None}

    async def scout_node(state: AgentState) -> dict[str, object]:
        try:
            route_map: RouteMap = await scout.scout(
                state["command"], max_steps=scout_max_steps, research_result=state.get("research_result")
            )
            if route_map.scout_completed:
                return {"route_map": route_map, "done": True}
            return {"route_map": route_map}
        except Exception as e:
            logger.warning("Scout failed: %s. Falling back to blind planning.", e)
            return {"route_map": None}

    async def planner_node(state: AgentState) -> dict[str, object]:
        plan = state["plan"]

        user_feedback = state.get("user_feedback")
        if user_feedback and plan is not None:
            failed_task = plan.tasks[0] if plan.tasks else Task(description="")
            replanned = await planner.replan(plan, failed_task, user_feedback)
            replanned.anchor = plan.anchor
            if not replanned.tasks:
                return {
                    "plan": replanned,
                    "done": True,
                    "retry_count": 0,
                    "current_task_idx": 0,
                    "eval_result": None,
                    "user_feedback": None,
                }
            return {
                "plan": replanned,
                "current_task_idx": 0,
                "retry_count": 0,
                "eval_result": None,
                "error": None,
                "plan_approved": False,
                "user_feedback": None,
            }

        if plan is None:
            new_plan = await planner.create_plan(
                state["command"],
                route_map=state.get("route_map"),
                research_result=state.get("research_result"),
            )
            if not new_plan.tasks:
                return {"plan": new_plan, "done": True, "retry_count": 0, "current_task_idx": 0, "eval_result": None}
            return {"plan": new_plan, "current_task_idx": 0, "retry_count": 0, "eval_result": None, "error": None}

        if len(state["completed_tasks"]) >= MAX_COMPLETED_TASKS:
            logger.warning("Completed-task cap reached (%d). Finishing gracefully.", MAX_COMPLETED_TASKS)
            return {
                "done": True,
                "error": f"Completed-task cap reached ({MAX_COMPLETED_TASKS})",
                "retry_count": 0,
                "eval_result": None,
            }

        eval_result = state["eval_result"]
        if eval_result is not None and not eval_result.success:
            failed_task = _current_task(state)
            if failed_task is None:
                return {"done": True, "error": eval_result.reason}
            replanned = await planner.replan(plan, failed_task, eval_result.reason)
            if not replanned.tasks:
                return {"plan": replanned, "done": True, "retry_count": 0, "current_task_idx": 0, "eval_result": None}
            return {"plan": replanned, "current_task_idx": 0, "eval_result": None, "error": None}

        if state["current_task_idx"] >= len(plan.tasks):
            next_plan = await planner.next_tasks(plan, state["completed_tasks"])
            if not next_plan.tasks:
                return {"plan": next_plan, "done": True, "retry_count": 0, "eval_result": None}
            if _is_repeated_plan(next_plan.tasks, state["completed_tasks"]):
                logger.warning("Planner produced only repeated tasks. Finishing gracefully.")
                return {
                    "plan": next_plan,
                    "done": True,
                    "error": "Planner repeated completed tasks",
                    "retry_count": 0,
                    "eval_result": None,
                }
            return {
                "plan": next_plan,
                "current_task_idx": 0,
                "retry_count": 0,
                "eval_result": None,
                "error": None,
                "plan_approved": False,
            }

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

    def plan_approval_node(state: AgentState) -> dict[str, object]:
        plan = state["plan"]
        if plan is None:
            return {"done": True}
        route_map = state.get("route_map")

        result = interrupt(
            {
                "type": "plan_approval",
                "plan": plan.model_dump(),
                "route_map": route_map.model_dump() if route_map else None,
            }
        )

        modification = result.get("modification")
        if modification:
            return {"user_feedback": modification, "plan_approved": False}

        if not result.get("approved", False):
            return {"done": True}
        return {"plan_approved": True, "user_feedback": None}

    def human_gateway_node(state: AgentState) -> dict[str, object]:
        eval_result = state.get("eval_result")
        failed_task = _current_task(state)
        result = interrupt(
            {
                "type": "human_gateway",
                "failed_task": failed_task.description if failed_task else "unknown",
                "reason": eval_result.reason if eval_result else "unknown",
                "retry_count": state["retry_count"],
            }
        )
        if not result.get("approved"):
            return {"done": True}
        user_input = result.get("feedback", "")
        return {"retry_count": 0, "user_feedback": user_input}

    def completion_check_node(state: AgentState) -> dict[str, object]:
        plan = state["plan"]
        anchor = plan.anchor if plan else "작업"
        completed_count = len(state["completed_tasks"])

        result = interrupt(
            {
                "type": "completion_check",
                "anchor": anchor,
                "completed_count": completed_count,
            }
        )
        if not result.get("approved"):
            return {"done": True}
        return {}

    def route_after_scout(state: AgentState) -> Literal["planner", "END"]:
        if state.get("done", False):
            return "END"
        return "planner"

    def route_after_planner(state: AgentState) -> Literal["plan_approval", "actor", "END"]:
        if state["done"]:
            return "END"
        task = _current_task(state)
        if task is None:
            return "END"
        if not state["plan_approved"]:
            return "plan_approval"
        return "actor"

    def route_after_approval(state: AgentState) -> Literal["actor", "planner", "END"]:
        if state["done"]:
            return "END"
        if state.get("user_feedback"):
            return "planner"
        return "actor"

    def route_after_evaluator(
        state: AgentState,
    ) -> Literal["planner", "actor", "human_gateway", "completion_check", "END"]:
        if state["done"]:
            return "END"

        eval_result = state["eval_result"]
        if eval_result is None:
            return "END"

        if eval_result.success:
            task = _current_task(state)
            if task is not None:
                return "actor"
            return "completion_check"

        if state["retry_count"] <= state["max_retries"]:
            return "planner"
        return "human_gateway"

    def route_after_human(state: AgentState) -> Literal["planner", "END"]:
        if state["done"]:
            return "END"
        return "planner"

    def route_after_completion(state: AgentState) -> Literal["planner", "END"]:
        if state["done"]:
            return "END"
        return "planner"

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("research", research_node)
    graph_builder.add_node("scout", scout_node)
    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node("plan_approval", plan_approval_node)
    graph_builder.add_node("actor", actor_node)
    graph_builder.add_node("evaluator", evaluator_node)
    graph_builder.add_node("human_gateway", human_gateway_node)
    graph_builder.add_node("completion_check", completion_check_node)

    graph_builder.set_entry_point("research")

    graph_builder.add_edge("research", "scout")
    graph_builder.add_conditional_edges(
        "scout",
        route_after_scout,
        {
            "planner": "planner",
            "END": END,
        },
    )

    graph_builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "plan_approval": "plan_approval",
            "actor": "actor",
            "END": END,
        },
    )
    graph_builder.add_conditional_edges(
        "plan_approval",
        route_after_approval,
        {
            "actor": "actor",
            "planner": "planner",
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
            "completion_check": "completion_check",
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
    graph_builder.add_conditional_edges(
        "completion_check",
        route_after_completion,
        {
            "planner": "planner",
            "END": END,
        },
    )

    return graph_builder.compile(checkpointer=checkpointer)
