"""Phase 3 통합 검증 — Planner → Actor → Evaluator 수동 연결 테스트.

사용법:
1. Chrome을 --remote-debugging-port=9222로 실행:
   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222

2. ANTHROPIC_API_KEY 환경변수 설정:
   export ANTHROPIC_API_KEY=your_api_key

3. 스크립트 실행:
   python scripts/test_phase3.py
"""

import asyncio
import logging
import sys

from langchain_anthropic import ChatAnthropic

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.llm import LangChainLLMAdapter
from surfy.domain.services import ActorService, EvaluatorService, PlannerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CDP_URL = "http://localhost:9222"
MODEL_NAME = "claude-sonnet-4-20250514"


async def main():
    """Phase 3 통합 테스트 실행."""
    logger.info("=== Phase 3 Integration Test ===")
    logger.info(f"CDP URL: {CDP_URL}")
    logger.info(f"Model: {MODEL_NAME}")

    # 1. 어댑터 초기화 (factory method 사용)
    logger.info("\n--- Initializing adapters ---")
    try:
        browser = await BrowserUseAdapter.create(CDP_URL)
        logger.info("Browser adapter created")
    except Exception as e:
        logger.error(f"Failed to connect to Chrome: {e}")
        logger.error("Make sure Chrome is running with --remote-debugging-port=9222")
        sys.exit(1)

    chat_model = ChatAnthropic(model_name=MODEL_NAME, timeout=None, stop=None)
    llm = LangChainLLMAdapter(model=chat_model, use_vision=True)
    logger.info("LLM adapter created")

    # 2. 서비스 초기화
    planner = PlannerService(llm)
    actor = ActorService(browser, llm)
    evaluator = EvaluatorService(browser, llm)
    logger.info("Services initialized")

    # 3. 테스트 명령
    command = "네이버에서 날씨 검색 후 내일 기온 확인"
    logger.info(f"\n--- Test Command: {command} ---")

    try:
        # 4. Planner: Plan 생성
        logger.info("\n=== Step 1: Planner — Creating plan ===")
        plan = await planner.create_plan(command)
        logger.info(f"Anchor: {plan.anchor}")
        logger.info(f"Rationale: {plan.anchor_rationale}")
        logger.info(f"Tasks ({len(plan.tasks)}):")
        for i, task in enumerate(plan.tasks):
            logger.info(f"  [{i + 1}] {task.description}")
            logger.info(f"      Criteria: {task.success_criteria}")

        # 5. 각 Task 실행 및 평가
        completed_tasks = []
        for i, task in enumerate(plan.tasks):
            logger.info(f"\n=== Step 2.{i + 1}: Actor — Executing task ===")
            logger.info(f"Task: {task.description}")

            # Actor 실행
            step_result = await actor.execute_task(task)
            logger.info(f"Actor result: success={step_result.success}")
            logger.info(f"Actor message: {step_result.message}")

            if not step_result.success:
                logger.error(f"Task failed: {step_result.message}")
                # Replan 시도 가능
                logger.info("Attempting replan...")
                plan = await planner.replan(plan, task, step_result.message)
                logger.info(f"Replanned tasks: {[t.description for t in plan.tasks]}")
                break

            # Evaluator 판정 — Actor 완료 직후 페이지 상태 사용
            logger.info(f"\n=== Step 3.{i + 1}: Evaluator — Verifying task ===")
            page_state = step_result.page_state or await browser.get_page_state()
            eval_result = await evaluator.evaluate(task, page_state)
            logger.info(f"Evaluator result: success={eval_result.success}")
            logger.info(f"Evaluator reason: {eval_result.reason}")

            if eval_result.success:
                completed_tasks.append(task)
                logger.info(f"Task {i + 1} completed and verified!")
            else:
                logger.warning(f"Task {i + 1} not verified: {eval_result.reason}")
                # 여기서 replan 가능
                break

        # 6. 결과 요약
        logger.info("\n=== Summary ===")
        total_tasks = len(plan.tasks)
        logger.info(f"Total tasks: {total_tasks}")
        logger.info(f"Completed tasks: {len(completed_tasks)}")
        if total_tasks > 0:
            logger.info(f"Success rate: {len(completed_tasks) / total_tasks * 100:.1f}%")
        else:
            logger.info("Success rate: N/A (no tasks)")

        if total_tasks > 0 and len(completed_tasks) == total_tasks:
            logger.info("\n[SUCCESS] All tasks completed successfully!")
        else:
            logger.warning("\n[WARNING] Some tasks failed or were not verified")

    except Exception as e:
        logger.exception(f"Error during test: {e}")
        raise

    finally:
        logger.info("\n--- Cleaning up ---")
        await browser.close()
        logger.info("Browser closed")

    logger.info("\n=== Phase 3 Integration Test Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
