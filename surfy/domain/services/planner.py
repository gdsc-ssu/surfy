"""Planner 서비스 — 사용자 명령을 태스크로 분해.

Plan Anchor 패턴:
- anchor(불변 최종 목표)를 중심으로 rolling wave 계획 수립
- DOM을 보지 않고 추상적 레벨에서만 작업
- 실패 시 해당 구간만 재계획 (anchor와 성공한 태스크는 보존)

디버그:
    scripts/debug_planner.py 참고
"""

import logging

from surfy.domain.models import Task
from surfy.domain.models.plan import Plan
from surfy.domain.models.route import RouteMap
from surfy.domain.ports import LLMPort

logger = logging.getLogger(__name__)


class PlannerService:
    """사용자 명령을 태스크로 분해하는 전략 컴포넌트.

    WebAnchor 논문의 핵심: 첫 번째 계획 스텝이 틀리면 전체 성공률이 23~31% 하락.
    따라서 anchor(최종 목표)를 명확히 설정하고 이를 중심으로 계획을 수립한다.
    """

    def __init__(self, llm: LLMPort):
        self._llm = llm

    async def create_plan(self, command: str, route_map: RouteMap | None = None) -> Plan:
        """첫 호출: anchor 설정 + 첫 1~2 태스크 생성.

        Args:
            command: 사용자 명령
            route_map: Scout 단계에서 수집된 관찰 내용 (선택 사항)

        Returns:
            Plan: anchor, tasks, anchor_rationale을 포함한 계획
        """
        route_obs = self._format_route_observations(route_map) if route_map else ""
        logger.info(
            "Planner create_plan called (route_observations=%s)",
            "provided" if route_obs else "empty",
        )
        return await self._llm.plan(command, progress="", route_observations=route_obs)

    async def next_tasks(self, plan: Plan, completed_tasks: list[Task]) -> Plan:
        """이후 호출: anchor 유지, 진행 상황 기반으로 다음 태스크 생성.

        Rolling wave 방식으로 1~2개씩 태스크를 추가한다.

        Args:
            plan: 현재 계획 (anchor 포함)
            completed_tasks: 완료된 태스크 목록

        Returns:
            Plan: anchor는 유지, 새로운 tasks가 포함된 계획
        """
        progress = self._summarize_progress(completed_tasks)
        new_plan = await self._llm.plan(plan.anchor, progress, route_observations="")
        # anchor는 절대 변경 안 됨
        new_plan.anchor = plan.anchor
        return new_plan

    async def replan(self, plan: Plan, failed_task: Task, reason: str) -> Plan:
        """Replan: 실패 구간만 재계획, anchor와 성공한 태스크 보존.

        Args:
            plan: 현재 계획 (anchor 포함)
            failed_task: 실패한 태스크
            reason: 실패 이유

        Returns:
            Plan: anchor는 유지, 재계획된 tasks가 포함된 계획
        """
        progress = f"실패한 태스크: {failed_task.description}\n사유: {reason}"
        new_plan = await self._llm.plan(plan.anchor, progress, route_observations="")
        # anchor는 절대 변경 안 됨
        new_plan.anchor = plan.anchor
        return new_plan

    def _summarize_progress(self, completed_tasks: list[Task]) -> str:
        """완료된 태스크 목록을 요약.

        Args:
            completed_tasks: 완료된 태스크 목록

        Returns:
            str: 진행 상황 요약 문자열
        """
        if not completed_tasks:
            return ""
        return "완료된 태스크:\n" + "\n".join(f"- {task.description}" for task in completed_tasks)

    def _format_route_observations(self, route_map: RouteMap) -> str:
        """RouteMap을 LLM용 관찰 문자열로 변환.

        Args:
            route_map: Scout 단계에서 수집된 관찰 내용

        Returns:
            str: 포맷팅된 관찰 문자열
        """
        if not route_map.steps:
            return ""
        lines = [f"Scout 탐색 요약: {route_map.scout_summary}", ""]
        for i, step in enumerate(route_map.steps, 1):
            elements = ", ".join(step.observed_elements[:5])  # limit to 5 elements
            lines.append(f"Step {i}: {step.action_taken} → {step.url}")
            if elements:
                lines.append(f"  발견한 요소: {elements}")
            if step.notes:
                lines.append(f"  메모: {step.notes}")
        lines.append(f"\n최종 URL: {route_map.final_url}")
        return "\n".join(lines)
