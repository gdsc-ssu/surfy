"""Planner 서비스 — 사용자 명령을 태스크로 분해.

Plan Anchor 패턴:
- anchor(불변 최종 목표)를 중심으로 rolling wave 계획 수립
- DOM을 보지 않고 추상적 레벨에서만 작업
- 실패 시 해당 구간만 재계획 (anchor와 성공한 태스크는 보존)
"""

from surfy.domain.models import Task
from surfy.domain.models.plan import Plan
from surfy.domain.ports import LLMPort


class PlannerService:
    """사용자 명령을 태스크로 분해하는 전략 컴포넌트.

    WebAnchor 논문의 핵심: 첫 번째 계획 스텝이 틀리면 전체 성공률이 23~31% 하락.
    따라서 anchor(최종 목표)를 명확히 설정하고 이를 중심으로 계획을 수립한다.
    """

    def __init__(self, llm: LLMPort):
        self._llm = llm

    async def create_plan(self, command: str) -> Plan:
        """첫 호출: anchor 설정 + 첫 1~2 태스크 생성.

        Args:
            command: 사용자 명령

        Returns:
            Plan: anchor, tasks, anchor_rationale을 포함한 계획
        """
        return await self._llm.plan(command, progress="")

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
        new_plan = await self._llm.plan(plan.anchor, progress)
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
        new_plan = await self._llm.plan(plan.anchor, progress)
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


if __name__ == "__main__":
    """PlannerService 테스트 — Plan 객체 확인용.

    사용법:
        .env 파일에 ANTHROPIC_API_KEY 설정 후
        python -m surfy.domain.services.planner
    """
    import asyncio
    import json

    from surfy.container import Container

    async def main() -> tuple[Plan, Plan | None, Plan | None]:
        # DI 컨테이너로 LLM 어댑터 주입
        container = Container()
        llm = container.llm()
        planner = PlannerService(llm)

        # 테스트 명령
        command = "네이버에서 날씨 검색 후 내일 기온 확인"
        print(f"Command: {command}")
        print("-" * 50)

        # Plan 생성
        print("\n[1] create_plan 호출...")
        plan = await planner.create_plan(command)

        # Plan 객체 출력
        print("\n=== Plan 객체 ===")
        print(f"Type: {type(plan)}")
        print(f"Anchor: {plan.anchor}")
        print(f"Anchor Rationale: {plan.anchor_rationale}")
        print(f"Tasks ({len(plan.tasks)}):")
        for i, task in enumerate(plan.tasks):
            print(f"\n  [{i + 1}] Task:")
            print(f"      Description: {task.description}")
            print(f"      Success Criteria:")
            print(f"        - url_contains: {task.success_criteria.url_contains}")
            print(f"        - text_visible: {task.success_criteria.text_visible}")
            print(f"        - description: {task.success_criteria.description}")

        # JSON 출력
        print("\n=== Plan as JSON ===")
        print(json.dumps(plan.model_dump(), indent=2, ensure_ascii=False))

        # next_tasks 테스트
        new_plan = None
        print("\n" + "=" * 50)
        print("[2] next_tasks 호출 (첫 번째 태스크 완료 가정)...")
        if plan.tasks:
            completed = [plan.tasks[0]]
            new_plan = await planner.next_tasks(plan, completed)
            print(f"\nNew Anchor (should be same): {new_plan.anchor}")
            print(f"New Tasks ({len(new_plan.tasks)}):")
            for i, task in enumerate(new_plan.tasks):
                print(f"  [{i + 1}] {task.description}")

        # replan 테스트
        replanned = None
        print("\n" + "=" * 50)
        print("[3] replan 호출 (첫 번째 태스크 실패 가정)...")
        if plan.tasks:
            failed_task = plan.tasks[0]
            replanned = await planner.replan(plan, failed_task, "요소를 찾을 수 없음")
            print(f"\nReplanned Anchor (should be same): {replanned.anchor}")
            print(f"Replanned Tasks ({len(replanned.tasks)}):")
            for i, task in enumerate(replanned.tasks):
                print(f"  [{i + 1}] {task.description}")

        return plan, new_plan, replanned

    def run() -> tuple[Plan, Plan | None, Plan | None]:
        """동기 래퍼 — 새 이벤트 루프에서 실행."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(main())
        finally:
            loop.close()

    plan, new_plan, replanned = run()

    # 여기서 객체 확인 가능
    # 예: print(plan.tasks[0].success_criteria)
    # 또는 python -i 로 실행 후 대화형으로 확인
