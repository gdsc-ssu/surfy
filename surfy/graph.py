import hashlib
import logging
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from surfy.domain.models import ActionType, ActorOutput, EvalResult, HistoryEntry, RouteMap, SuccessCriteria, Task
from surfy.domain.models.research import ResearchResult
from surfy.domain.ports.cache import CachePort
from surfy.domain.ports.llm import LLMPort
from surfy.domain.services import (
    ActorService,
    EvaluatorService,
    PlannerService,
    ReporterService,
    ResearcherService,
    ScoutService,
)
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
    completed_descriptions = {task.description.strip().lower() for task in completed_tasks}
    for task in next_tasks:
        desc = task.description.strip().lower()
        for completed_desc in completed_descriptions:
            if desc in completed_desc or completed_desc in desc:
                return True
            common_words = set(desc.split()) & set(completed_desc.split())
            if len(common_words) >= min(3, len(desc.split())):
                return True
    return False


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
    reporter: ReporterService | None = None,
    researcher: ResearcherService | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    scout_max_steps: int = 20,
    handoff_on_auth: bool = True,
    cache: CachePort | None = None,
    llm: LLMPort | None = None,
) -> CompiledStateGraph:
    async def _cache_key(command: str) -> str:
        if llm is None:
            return hashlib.sha256(command.lower().strip().encode()).hexdigest()[:16]
        intent = await llm.extract_intent(command)
        parts = [intent.service]
        if intent.from_location:
            parts.append(intent.from_location)
        if intent.to_location:
            parts.append(intent.to_location)
        parts.append(intent.action)
        return ":".join(p.lower() for p in parts)

    async def cache_lookup_node(state: AgentState) -> dict[str, object]:
        if cache is None:
            return {"cache_hit": False}
        key = await _cache_key(state["command"])
        scenario = cache.get(key)
        if scenario is None:
            return {"cache_hit": False}
        logger.info("Cache hit: key=%s command=%s", key, state["command"][:50])
        return {
            "cache_hit": True,
            "route_map": scenario.route_map,
            "plan": scenario.plan,
            "current_task_idx": 0,
            "retry_count": 0,
            "eval_result": None,
            "error": None,
        }

    async def cache_store_node(state: AgentState) -> dict[str, object]:
        if cache is None or state.get("cache_hit", False):
            return {}
        route_map = state.get("route_map")
        plan = state.get("plan")
        if route_map is None or plan is None:
            return {}
        from surfy.domain.models.cache import CachedScenario
        command = state["command"]
        key = await _cache_key(command)
        cache.set(CachedScenario(
            cache_key=key,
            command_normalized=command.lower().strip(),
            route_map=route_map,
            plan=plan,
        ))
        return {}

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
            if route_map and route_map.scout_completed:
                logger.info("Scout already extracted data. Skipping planner.")
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
            replanned = await planner.replan(
                plan, failed_task, user_feedback, completed_tasks=list(state["completed_tasks"])
            )
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
            replanned = await planner.replan(
                plan, failed_task, eval_result.reason, completed_tasks=list(state["completed_tasks"])
            )
            if not replanned.tasks:
                return {"plan": replanned, "done": True, "retry_count": 0, "current_task_idx": 0, "eval_result": None}
            return {
                "plan": replanned,
                "current_task_idx": 0,
                "eval_result": None,
                "error": None,
                "plan_approved": False,
            }

        if state["current_task_idx"] >= len(plan.tasks):
            completed = list(state["completed_tasks"])
            if len(completed) >= 10:
                logger.warning("Max completed tasks (10) reached. Finishing.")
                return {"plan": plan, "done": True, "retry_count": 0, "eval_result": None}
            has_results = any(t.result and t.result != "완료" for t in completed)
            if has_results and len(completed) >= 2:
                logger.info("Tasks have meaningful results. Finishing without asking planner for more.")
                return {"plan": plan, "done": True, "retry_count": 0, "eval_result": None}
            next_plan = await planner.next_tasks(plan, completed)
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

        plan = state.get("plan")
        command = state.get("command", "")
        if plan and getattr(plan, "anchor", None):
            task = Task(
                description=f"[사용자 원래 명령: {command}]\n[최종 목표: {plan.anchor}]\n\n{task.description}",
                success_criteria=task.success_criteria,
                target_url=task.target_url,
            )

        post_auth = state.get("post_auth", False)
        initial_memory = (
            "[인증 완료] 사용자가 인증/로그인을 완료했습니다. 인증 이후 단계를 계속 진행하세요."
            if post_auth
            else ""
        )
        result = await actor.execute_task(task, initial_memory=initial_memory)
        action_type = ActionType.DONE if result.success else ActionType.STUCK
        summary_action = ActorOutput(thinking=task.description, action_type=action_type, value=result.message)
        history_entry = HistoryEntry(action=summary_action, result=result, step=None)

        is_auth = not result.success and result.message is not None and "AUTH_REQUIRED" in result.message

        return {
            "history": [history_entry],
            "last_page_state": result.page_state,
            "error": None if result.success else result.message,
            "auth_required": is_auth,
            "post_auth": False,
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
            actor_message = ""
            if state["history"]:
                last_entry = state["history"][-1]
                if last_entry.result and last_entry.result.message:
                    actor_message = last_entry.result.message
            if actor_message and actor_message != "Task completed":
                result_text = actor_message
            elif page_state is not None:
                result_text = f"[{page_state.title}] {page_state.url}"
            else:
                result_text = "완료"
            task = task.model_copy(update={"result": result_text})
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

    async def human_gateway_node(state: AgentState) -> dict[str, object]:
        eval_result = state.get("eval_result")
        failed_task = _current_task(state)
        is_auth = state.get("auth_required", False)
        interrupt_type = "auth_required" if is_auth else "human_gateway"
        result = interrupt(
            {
                "type": interrupt_type,
                "failed_task": failed_task.description if failed_task else "unknown",
                "reason": eval_result.reason if eval_result else "unknown",
                "retry_count": state["retry_count"],
            }
        )
        if not result.get("approved"):
            return {"done": True}
        if is_auth:
            page_before = state.get("last_page_state")
            page_after = await actor._browser.get_page_state()

            login_completed = (
                page_before is None
                or page_before.url != page_after.url
                or page_before.dom_text[:300] != page_after.dom_text[:300]
            )

            if not login_completed:
                result2 = interrupt(
                    {
                        "type": "auth_verify_failed",
                        "message": "아직 로그인 전과 동일한 페이지입니다. 로그인 완료 후 다시 확인해주세요.",
                    }
                )
                if not result2.get("approved"):
                    return {"done": True}

            return {"retry_count": 0, "eval_result": None, "auth_required": False, "post_auth": True, "error": None}
        return {"retry_count": 0}

    async def completion_check_node(state: AgentState) -> dict[str, object]:
        plan = state["plan"]
        anchor = plan.anchor if plan else "작업"
        completed_count = len(state["completed_tasks"])

        last_page_state = state.get("last_page_state")
        if llm is not None and last_page_state is not None:
            eval_result = await llm.evaluate(
                SuccessCriteria(description=anchor),
                last_page_state,
            )
            if not eval_result.success:
                logger.info("completion_check: anchor not achieved (%s), routing to planner", eval_result.reason)
                return {}

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

    def route_after_cache_lookup(state: AgentState) -> Literal["research", "plan_approval"]:
        return "plan_approval" if state.get("cache_hit", False) else "research"

    async def report_node(state: AgentState) -> dict[str, object]:
        if reporter is None:
            return {"report_result": None}
        command = state["command"]
        completed_tasks = list(state["completed_tasks"])

        if not completed_tasks:
            route_map = state.get("route_map")
            scout_summary = (route_map.scout_summary if route_map else "") or ""
            raw_research = state.get("research_result")
            research_summary = raw_research.summary if raw_research and hasattr(raw_research, "summary") else ""
            context = scout_summary or research_summary
            if context:
                completed_tasks = [Task(description="수집된 정보", result=context)]

        try:
            report_text = await reporter.report(command, completed_tasks)
            return {"report_result": report_text}
        except Exception as e:
            logger.warning("Report generation failed: %s", e)
            return {"report_result": None}

    def route_after_scout(state: AgentState) -> Literal["planner", "report"]:
        if state.get("done", False):
            return "report"
        return "planner"

    def route_after_planner(state: AgentState) -> Literal["plan_approval", "actor", "cache_store", "END"]:
        if state["done"]:
            return "cache_store"
        task = _current_task(state)
        if task is None:
            return "END"
        if not state["plan_approved"]:
            return "plan_approval"
        return "actor"

    def route_after_approval(state: AgentState) -> Literal["actor", "planner", "cache_store", "END"]:
        if state["done"]:
            return "cache_store"
        if state.get("user_feedback"):
            return "planner"
        return "actor"

    def route_after_evaluator(
        state: AgentState,
    ) -> Literal["planner", "actor", "human_gateway", "completion_check", "cache_store", "END"]:
        if state["done"]:
            return "cache_store"

        eval_result = state["eval_result"]
        if eval_result is None:
            return "END"

        if eval_result.success:
            task = _current_task(state)
            if task is not None:
                return "actor"
            return "completion_check"

        if state.get("auth_required") and handoff_on_auth:
            return "human_gateway"

        if state["retry_count"] <= state["max_retries"]:
            return "planner"
        return "human_gateway"

    def route_after_human(state: AgentState) -> Literal["planner", "cache_store", "END"]:
        if state["done"]:
            return "cache_store"
        return "planner"

    def route_after_completion(state: AgentState) -> Literal["planner", "cache_store"]:
        if state["done"]:
            return "cache_store"
        return "planner"

    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("cache_lookup", cache_lookup_node)
    graph_builder.add_node("research", research_node)
    graph_builder.add_node("scout", scout_node)
    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node("cache_store", cache_store_node)
    graph_builder.add_node("plan_approval", plan_approval_node)
    graph_builder.add_node("actor", actor_node)
    graph_builder.add_node("evaluator", evaluator_node)
    graph_builder.add_node("human_gateway", human_gateway_node)
    graph_builder.add_node("completion_check", completion_check_node)
    graph_builder.add_node("report", report_node)

    graph_builder.set_entry_point("cache_lookup")

    graph_builder.add_conditional_edges(
        "cache_lookup",
        route_after_cache_lookup,
        {"research": "research", "plan_approval": "plan_approval"},
    )
    graph_builder.add_edge("research", "scout")
    graph_builder.add_conditional_edges(
        "scout",
        route_after_scout,
        {
            "planner": "planner",
            "report": "report",
        },
    )

    graph_builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "plan_approval": "plan_approval",
            "actor": "actor",
            "cache_store": "cache_store",
            "END": END,
        },
    )
    graph_builder.add_conditional_edges(
        "plan_approval",
        route_after_approval,
        {
            "actor": "actor",
            "planner": "planner",
            "cache_store": "cache_store",
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
            "cache_store": "cache_store",
            "END": END,
        },
    )
    graph_builder.add_conditional_edges(
        "human_gateway",
        route_after_human,
        {
            "planner": "planner",
            "cache_store": "cache_store",
            "END": END,
        },
    )
    graph_builder.add_conditional_edges(
        "completion_check",
        route_after_completion,
        {
            "planner": "planner",
            "cache_store": "cache_store",
        },
    )
    graph_builder.add_edge("cache_store", "report")
    graph_builder.add_edge("report", END)

    return graph_builder.compile(checkpointer=checkpointer)
