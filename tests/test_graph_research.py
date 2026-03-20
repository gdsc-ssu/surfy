from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from surfy.domain.models import EvalResult, PageState, RouteMap, RouteStep, StepResult, SuccessCriteria, Task
from surfy.domain.models.plan import Plan
from surfy.domain.models.research import ResearchResult
from surfy.graph import _is_simple_navigation_command, compile_graph


def _initial_state(command: str) -> dict:
    return {
        "command": command,
        "plan": None,
        "route_map": None,
        "current_task_idx": 0,
        "eval_result": None,
        "retry_count": 0,
        "max_retries": 1,
        "history": [],
        "completed_tasks": [],
        "last_page_state": None,
        "plan_approved": False,
        "user_feedback": None,
        "research_result": None,
        "auth_required": False,
        "post_auth": False,
        "done": False,
        "error": None,
    }


def _build_graph(researcher):
    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://example.com", scout_summary="요약"))

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=Plan(anchor="a", tasks=[], anchor_rationale="r"))
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    actor = MagicMock()
    evaluator = MagicMock()

    return compile_graph(scout=scout, planner=planner, actor=actor, evaluator=evaluator, researcher=researcher)


def test_is_simple_navigation_command_with_url():
    assert _is_simple_navigation_command("https://example.com") is True


def test_is_simple_navigation_command_with_short_text():
    assert _is_simple_navigation_command("네이버") is True


def test_is_simple_navigation_command_with_normal_command():
    assert _is_simple_navigation_command("네이버에서 오늘 날씨 검색") is False


@pytest.mark.asyncio
async def test_research_node_skips_simple_navigation_command():
    researcher = MagicMock()
    researcher.research = AsyncMock()
    graph = _build_graph(researcher=researcher)

    result = await graph.ainvoke(_initial_state("https://example.com"))

    assert result["research_result"] is None
    researcher.research.assert_not_awaited()


@pytest.mark.asyncio
async def test_research_node_runs_and_stores_result_for_complex_command():
    researcher = MagicMock()
    research_result = ResearchResult(summary="요약", sources=["https://a.com"], raw_results=[])
    researcher.research = AsyncMock(return_value=research_result)
    graph = _build_graph(researcher=researcher)

    result = await graph.ainvoke(_initial_state("파이썬 비동기 처리 방법 조사"))

    assert result["research_result"] == research_result
    researcher.research.assert_awaited_once_with("파이썬 비동기 처리 방법 조사")


@pytest.mark.asyncio
async def test_research_node_handles_researcher_failure():
    researcher = MagicMock()
    researcher.research = AsyncMock(side_effect=RuntimeError("timeout"))
    graph = _build_graph(researcher=researcher)

    result = await graph.ainvoke(_initial_state("LLM 벤치마크 비교 분석"))

    assert result["research_result"] is None


@pytest.mark.asyncio
async def test_scout_completed_skips_planner():
    """scout_completed=True이면 planner를 건너뛰고 report로 간다."""
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)

    scout = MagicMock()
    scout.scout = AsyncMock(
        return_value=RouteMap(
            steps=[], final_url="https://example.com", scout_summary="완료", scout_completed=True
        )
    )

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=Plan(anchor="목표", tasks=[], anchor_rationale="r"))
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    actor = MagicMock()
    evaluator = MagicMock()
    graph = compile_graph(scout=scout, planner=planner, actor=actor, evaluator=evaluator, researcher=researcher)

    result = await graph.ainvoke(_initial_state("네이버 열어"))

    assert result["route_map"].scout_completed is True
    assert result["done"] is True
    planner.create_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_scout_completed_skips_planner_and_goes_to_report():
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=ResearchResult(summary="요약", sources=[], raw_results=[]))

    scout = MagicMock()
    route_map = RouteMap(
        steps=[
            RouteStep(
                url="https://example.com",
                title="제목",
                action_taken="관찰",
                observed_elements=[],
                notes="데이터 발견",
            )
        ],
        final_url="https://example.com",
        scout_summary="데이터",
        scout_completed=True,
    )
    scout.scout = AsyncMock(return_value=route_map)

    planner = MagicMock()
    planner.create_plan = AsyncMock()

    actor = MagicMock()
    evaluator = MagicMock()

    reporter = MagicMock()
    reporter.report = AsyncMock(return_value="최종 리포트")

    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        reporter=reporter,
        checkpointer=MemorySaver(),
        handoff_on_auth=False,
    )

    config = cast(RunnableConfig, {"configurable": {"thread_id": "scout_fast_path"}})
    result = await graph.ainvoke(_initial_state("데이터 찾아줘"), config)

    state = await graph.aget_state(config)
    assert state.next == ()
    assert result["done"] is True
    assert result["report_result"] == "최종 리포트"

    planner.create_plan.assert_not_awaited()
    reporter.report.assert_awaited_once()


@pytest.mark.asyncio
async def test_scout_not_completed_routes_to_planner():
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)
    graph = _build_graph(researcher=researcher)

    result = await graph.ainvoke(_initial_state("네이버에서 날씨 검색"))

    assert result["done"] is True
    assert result["plan"] is not None


@pytest.mark.asyncio
async def test_scout_exception_falls_through_to_planner():
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)

    scout = MagicMock()
    scout.scout = AsyncMock(side_effect=RuntimeError("browser crash"))

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=Plan(anchor="a", tasks=[], anchor_rationale="r"))
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    actor = MagicMock()
    evaluator = MagicMock()
    graph = compile_graph(scout=scout, planner=planner, actor=actor, evaluator=evaluator, researcher=researcher)

    result = await graph.ainvoke(_initial_state("네이버 열어"))

    assert result["route_map"] is None
    planner.create_plan.assert_awaited_once()


@pytest.mark.asyncio
async def test_plan_approval_interrupt_payload_contains_plan_and_route_map():
    researcher = MagicMock()
    researcher.research = AsyncMock(
        return_value=ResearchResult(summary="요약", sources=["https://a.com"], raw_results=[])
    )

    scout = MagicMock()
    route_map = RouteMap(
        steps=[
            RouteStep(
                url="https://example.com/search",
                title="검색",
                action_taken="검색어 입력",
                observed_elements=["검색창"],
                notes="정상",
            )
        ],
        final_url="https://example.com/result",
        scout_summary="검색 결과 페이지로 이동 가능",
    )
    scout.scout = AsyncMock(return_value=route_map)

    planner = MagicMock()
    plan = Plan(
        anchor="결과 확인",
        anchor_rationale="핵심 결과 페이지 진입이 목표",
        tasks=[
            Task(
                description="결과 링크 클릭",
                target_url="https://example.com/result",
                success_criteria=SuccessCriteria(text_visible="결과"),
            )
        ],
    )
    planner.create_plan = AsyncMock(return_value=plan)
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    actor = MagicMock()
    evaluator = MagicMock()
    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        checkpointer=MemorySaver(),
        handoff_on_auth=False,
    )

    config = cast(RunnableConfig, {"configurable": {"thread_id": "research_interrupt_payload"}})
    async for _ in graph.astream(_initial_state("복잡한 검색 요청"), config):
        pass

    state = await graph.aget_state(config)
    assert state.next == ("plan_approval",)
    interrupt_payload = state.tasks[0].interrupts[0].value
    assert interrupt_payload["type"] == "plan_approval"
    assert interrupt_payload["plan"] == plan.model_dump()
    assert interrupt_payload["route_map"] == route_map.model_dump()


@pytest.mark.asyncio
async def test_plan_modification_resume_triggers_replan_and_new_approval_interrupt():
    researcher = MagicMock()
    researcher.research = AsyncMock(
        return_value=ResearchResult(summary="요약", sources=["https://a.com"], raw_results=[])
    )

    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://example.com", scout_summary="요약"))

    planner = MagicMock()
    initial_plan = Plan(
        anchor="결과 확인",
        anchor_rationale="초기 계획",
        tasks=[Task(description="초기 태스크", success_criteria=SuccessCriteria(text_visible="초기"))],
    )
    replanned = Plan(
        anchor="결과 확인",
        anchor_rationale="수정 반영",
        tasks=[Task(description="수정된 태스크", success_criteria=SuccessCriteria(text_visible="수정"))],
    )
    planner.create_plan = AsyncMock(return_value=initial_plan)
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock(return_value=replanned)

    actor = MagicMock()
    evaluator = MagicMock()
    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        checkpointer=MemorySaver(),
        handoff_on_auth=False,
    )

    config = cast(RunnableConfig, {"configurable": {"thread_id": "plan_modification_replan"}})
    async for _ in graph.astream(_initial_state("복잡한 검색 요청"), config):
        pass

    before_resume = await graph.aget_state(config)
    assert before_resume.next == ("plan_approval",)

    modification = "검색 대신 뉴스 탭으로 바로 가도록 바꿔줘"
    resume_events: list[dict] = []
    async for event in graph.astream(Command(resume={"approved": False, "modification": modification}), config):
        resume_events.append(event)

    plan_approval_updates = [
        updates for event in resume_events for node_name, updates in event.items() if node_name == "plan_approval"
    ]
    assert any(update.get("user_feedback") == modification for update in plan_approval_updates)

    planner.replan.assert_awaited_once()
    assert planner.replan.await_args.args[2] == modification

    after_resume = await graph.aget_state(config)
    assert after_resume.next == ("plan_approval",)


@pytest.mark.asyncio
async def test_eval_failure_replan_resets_plan_approved_and_requires_reapproval():
    """#62 재현: eval 실패 → replan 후 plan_approved=False 리셋 → 새 approval interrupt 발생."""
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)

    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://srt.com", scout_summary="SRT"))

    page_state = PageState(url="https://srt.com", title="SRT", dom_text="출발역 입력")

    initial_plan = Plan(
        anchor="SRT 예약",
        anchor_rationale="예약 흐름",
        tasks=[Task(description="출발역 선택", success_criteria=SuccessCriteria(text_visible="출발역"))],
    )
    replanned = Plan(
        anchor="SRT 예약",
        anchor_rationale="다른 접근",
        tasks=[Task(description="다른 방식으로 출발역 선택", success_criteria=SuccessCriteria(text_visible="출발역"))],
    )

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=initial_plan)
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock(return_value=replanned)

    actor = MagicMock()
    actor.execute_task = AsyncMock(
        return_value=StepResult(success=False, message="Loop detected", page_state=page_state)
    )

    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value=EvalResult(success=False, reason="출발역 미선택"))

    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        checkpointer=MemorySaver(),
        handoff_on_auth=False,
    )

    config = cast(RunnableConfig, {"configurable": {"thread_id": "eval_failure_replan_approval"}})

    async for _ in graph.astream(_initial_state("SRT 예약"), config):
        pass

    state_before = await graph.aget_state(config)
    assert state_before.next == ("plan_approval",)

    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass

    planner.replan.assert_awaited_once()

    state_after = await graph.aget_state(config)
    assert state_after.next == ("plan_approval",), "replan 후 plan_approved=False여야 새 approval interrupt 발생"


@pytest.mark.asyncio
async def test_eval_failure_replan_passes_completed_tasks_to_planner():
    """#62 재현: replan 시 completed_tasks 컨텍스트가 planner.replan에 전달됨."""
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)

    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://ex.com", scout_summary="요약"))

    page_state = PageState(url="https://ex.com/step2", title="Step 2", dom_text="content")

    task_a = Task(description="태스크 A", success_criteria=SuccessCriteria(text_visible="A 완료"))
    task_b = Task(description="태스크 B", success_criteria=SuccessCriteria(text_visible="B 완료"))

    initial_plan = Plan(anchor="목표", anchor_rationale="이유", tasks=[task_a, task_b])
    replanned = Plan(
        anchor="목표", anchor_rationale="재계획", tasks=[Task(description="태스크 B 재시도")]
    )

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=initial_plan)
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock(return_value=replanned)

    call_count = 0

    async def actor_side_effect(task, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return StepResult(success=True, message="A 완료", page_state=page_state)
        return StepResult(success=False, message="B 실패", page_state=page_state)

    actor = MagicMock()
    actor.execute_task = AsyncMock(side_effect=actor_side_effect)

    eval_count = 0

    async def eval_side_effect(task, ps):
        nonlocal eval_count
        eval_count += 1
        if eval_count == 1:
            return EvalResult(success=True, reason="A 성공")
        return EvalResult(success=False, reason="B 실패")

    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(side_effect=eval_side_effect)

    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        checkpointer=MemorySaver(),
        handoff_on_auth=False,
    )

    config = cast(RunnableConfig, {"configurable": {"thread_id": "eval_replan_completed_tasks"}})

    async for _ in graph.astream(_initial_state("목표 달성"), config):
        pass

    state1 = await graph.aget_state(config)
    assert state1.next == ("plan_approval",)

    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass

    planner.replan.assert_awaited_once()
    replan_kwargs = planner.replan.await_args.kwargs
    assert "completed_tasks" in replan_kwargs
    completed = replan_kwargs["completed_tasks"]
    assert len(completed) == 1
    assert completed[0].description == "태스크 A"


@pytest.mark.asyncio
async def test_auth_required_routes_to_human_gateway_immediately():
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)

    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://gov.kr", scout_summary="정부24"))

    page_state = PageState(url="https://gov.kr/auth", title="본인인증", dom_text="인증 필요")
    initial_plan = Plan(
        anchor="등본 발급",
        anchor_rationale="발급 흐름",
        tasks=[Task(description="등본 신청", success_criteria=SuccessCriteria(text_visible="신청"))],
    )

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=initial_plan)
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    actor = MagicMock()
    actor.execute_task = AsyncMock(
        return_value=StepResult(success=False, message="AUTH_REQUIRED: 본인인증 필요", page_state=page_state)
    )

    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value=EvalResult(success=False, reason="인증 페이지"))

    graph = compile_graph(
        scout=scout, planner=planner, actor=actor, evaluator=evaluator,
        researcher=researcher, checkpointer=MemorySaver(), handoff_on_auth=True,
    )

    config = cast(RunnableConfig, {"configurable": {"thread_id": "auth_handoff_immediate"}})

    async for _ in graph.astream(_initial_state("등본 발급"), config):
        pass
    state1 = await graph.aget_state(config)
    assert state1.next == ("plan_approval",)

    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass

    planner.replan.assert_not_awaited()

    state2 = await graph.aget_state(config)
    assert state2.next == ("human_gateway",)

    payload = state2.tasks[0].interrupts[0].value
    assert payload["type"] == "auth_required"


@pytest.mark.asyncio
async def test_auth_handoff_disabled_falls_through_to_retry():
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)

    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://gov.kr", scout_summary="정부24"))

    page_state = PageState(url="https://gov.kr/auth", title="본인인증", dom_text="인증 필요")
    initial_plan = Plan(
        anchor="등본 발급", anchor_rationale="발급 흐름",
        tasks=[Task(description="등본 신청", success_criteria=SuccessCriteria(text_visible="신청"))],
    )
    replanned = Plan(
        anchor="등본 발급", anchor_rationale="재시도",
        tasks=[Task(description="다른 방법 시도")],
    )

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=initial_plan)
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock(return_value=replanned)

    actor = MagicMock()
    actor.execute_task = AsyncMock(
        return_value=StepResult(success=False, message="AUTH_REQUIRED: 본인인증 필요", page_state=page_state)
    )

    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value=EvalResult(success=False, reason="인증 페이지"))

    graph = compile_graph(
        scout=scout, planner=planner, actor=actor, evaluator=evaluator,
        researcher=researcher, checkpointer=MemorySaver(), handoff_on_auth=False,
    )

    config = cast(RunnableConfig, {"configurable": {"thread_id": "auth_handoff_disabled"}})

    async for _ in graph.astream(_initial_state("등본 발급"), config):
        pass

    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass

    planner.replan.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_resume_clears_stale_state_and_retries_task():
    researcher = MagicMock()
    researcher.research = AsyncMock(return_value=None)

    scout = MagicMock()
    scout.scout = AsyncMock(return_value=RouteMap(steps=[], final_url="https://gov.kr", scout_summary="정부24"))

    auth_page = PageState(url="https://gov.kr/auth", title="본인인증", dom_text="인증 필요")
    success_page = PageState(url="https://gov.kr/done", title="신청완료", dom_text="신청 완료")

    initial_plan = Plan(
        anchor="등본 발급", anchor_rationale="발급 흐름",
        tasks=[Task(description="등본 신청", success_criteria=SuccessCriteria(text_visible="신청"))],
    )

    planner = MagicMock()
    planner.create_plan = AsyncMock(return_value=initial_plan)
    planner.next_tasks = AsyncMock()
    planner.replan = AsyncMock()

    call_count = 0

    async def actor_side_effect(task, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return StepResult(success=False, message="AUTH_REQUIRED: 본인인증 필요", page_state=auth_page)
        return StepResult(success=True, message="신청 완료", page_state=success_page)

    actor = MagicMock()
    actor.execute_task = AsyncMock(side_effect=actor_side_effect)
    actor._browser.get_page_state = AsyncMock(return_value=success_page)

    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(
        side_effect=[
            EvalResult(success=False, reason="인증 페이지"),
            EvalResult(success=True, reason="신청 완료"),
        ]
    )

    graph = compile_graph(
        scout=scout, planner=planner, actor=actor, evaluator=evaluator,
        researcher=researcher, checkpointer=MemorySaver(), handoff_on_auth=True,
    )

    config = cast(RunnableConfig, {"configurable": {"thread_id": "auth_resume_clear"}})

    async for _ in graph.astream(_initial_state("등본 발급"), config):
        pass
    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass

    state_at_gateway = await graph.aget_state(config)
    assert state_at_gateway.next == ("human_gateway",)

    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass

    planner.replan.assert_not_awaited()
    assert call_count == 2

    state_final = await graph.aget_state(config)
    assert state_final.values.get("auth_required") is False
    assert state_final.values.get("error") is None


@pytest.mark.asyncio
async def test_completion_check_approved_false_routes_to_done():
    """completion_check에서 approved=False(Complete) → done=True → cache_store → END."""
    researcher = MagicMock()
    scout = MagicMock()
    route_map = RouteMap(steps=[], final_url="https://example.com", scout_summary="요약")
    scout.scout = AsyncMock(return_value=route_map)
    planner = MagicMock()
    dummy_plan = Plan(
        anchor="테스트",
        anchor_rationale="테스트용",
        tasks=[Task(description="태스크 1", success_criteria=SuccessCriteria(text_visible="완료"))],
    )
    planner.create_plan = AsyncMock(return_value=dummy_plan)
    planner.replan = AsyncMock(return_value=dummy_plan)
    planner.next_tasks = AsyncMock(return_value=dummy_plan)
    page_state = PageState(url="https://example.com", title="테스트", dom_text="완료")
    actor = MagicMock()
    actor.execute_task = AsyncMock(return_value=StepResult(success=True, message="OK", page_state=page_state))

    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value=EvalResult(success=True, reason="완료"))

    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        checkpointer=MemorySaver(),
        handoff_on_auth=False,
    )

    initial_state = _initial_state("명령")
    initial_state.update({"route_map": route_map, "last_page_state": page_state})

    config = cast(RunnableConfig, {"configurable": {"thread_id": "completion_false"}})

    async for _ in graph.astream(initial_state, config):
        pass
    state = await graph.aget_state(config)
    assert state.next == ("plan_approval",)

    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass
    state = await graph.aget_state(config)
    assert state.next == ("completion_check",)

    async for _ in graph.astream(Command(resume={"approved": False}), config):
        pass
    final_state = await graph.aget_state(config)
    assert final_state.values["done"] is True
    assert final_state.next == ()


@pytest.mark.asyncio
async def test_completion_check_approved_true_routes_to_planner():
    """completion_check에서 approved=True(Request More) → planner 재진입."""
    researcher = MagicMock()
    scout = MagicMock()
    route_map = RouteMap(steps=[], final_url="https://example.com", scout_summary="요약")
    scout.scout = AsyncMock(return_value=route_map)
    planner = MagicMock()
    dummy_plan = Plan(
        anchor="테스트",
        anchor_rationale="테스트용",
        tasks=[Task(description="태스크 1", success_criteria=SuccessCriteria(text_visible="완료"))],
    )
    next_plan = Plan(
        anchor="테스트",
        anchor_rationale="테스트용",
        tasks=[Task(description="새로운 태스크", success_criteria=SuccessCriteria(text_visible="결과"))],
    )
    planner.create_plan = AsyncMock(return_value=dummy_plan)
    planner.replan = AsyncMock(return_value=dummy_plan)
    planner.next_tasks = AsyncMock(return_value=next_plan)
    page_state = PageState(url="https://example.com", title="테스트", dom_text="완료")
    actor = MagicMock()
    actor.execute_task = AsyncMock(return_value=StepResult(success=True, message="OK", page_state=page_state))

    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value=EvalResult(success=True, reason="완료"))

    graph = compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
        checkpointer=MemorySaver(),
        handoff_on_auth=False,
    )

    initial_state = _initial_state("명령")
    initial_state.update({"route_map": route_map, "last_page_state": page_state})

    config = cast(RunnableConfig, {"configurable": {"thread_id": "completion_true"}})

    async for _ in graph.astream(initial_state, config):
        pass
    state = await graph.aget_state(config)
    assert state.next == ("plan_approval",)

    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass
    state = await graph.aget_state(config)
    assert state.next == ("completion_check",)

    async for _ in graph.astream(Command(resume={"approved": True}), config):
        pass
    final_state = await graph.aget_state(config)
    assert final_state.next == ("plan_approval",)
    assert final_state.values.get("done") is not True
