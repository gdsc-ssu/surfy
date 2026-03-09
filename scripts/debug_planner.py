"""PlannerService 디버그용 스크립트 — Plan 객체 확인용.

사용법:
    PyCharm 콘솔에서:
        exec(open("scripts/debug_planner.py").read())

    또는 터미널에서:
        python scripts/debug_planner.py

    대화형 확인:
        python -i scripts/debug_planner.py
        >>> plan
        >>> plan.tasks[0].success_criteria
"""

import asyncio
import json

from surfy.container import Container
from surfy.domain.models.plan import Plan
from surfy.domain.services.planner import PlannerService


async def main() -> tuple[Plan, Plan | None, Plan | None]:
    """PlannerService 테스트 — Plan 객체 생성 및 확인."""
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
        print("      Success Criteria:")
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


if __name__ == "__main__":
    plan, new_plan, replanned = run()

    # 여기서 객체 확인 가능
    # python -i scripts/debug_planner.py 로 실행 후:
    # >>> plan
    # >>> plan.tasks[0].success_criteria
    # >>> plan.model_dump()
