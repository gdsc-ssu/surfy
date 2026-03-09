# Phase 3: Planner + Evaluator 구현 계획

## 개요

- **목표**: Planner + Evaluator 구현으로 Hierarchical Agent 완성
- **순서**: 의존성 기반 Step 1→6 (리뷰 피드백 반영)
- **테스트**: 각 서비스별 mock 단위 테스트 + 통합 검증 스크립트

## 현재 상황

### 완료된 작업 (Phase 1 & 2)
- **Phase 1**: BrowserPort, BrowserUseAdapter, 도메인 모델 (ActionType, BrowserAction, PageState, StepResult) ✅
- **Phase 2**: LLMPort (decide_action만), AnthropicAdapter (decide_action만), ActorService (ReAct loop) ✅

### Phase 3 Issue 현황 (모두 OPEN)

| Issue # | 제목 | 상태 |
|---------|------|------|
| #9 | Plan/Task/SuccessCriteria 모델 | OPEN |
| #10 | EvalResult + EvaluatorService | OPEN |
| #11 | PlannerService | OPEN |
| #12 | AnthropicAdapter — plan, evaluate 추가 | OPEN |
| #13 | 통합 검증 스크립트 | OPEN |

### 의존성 그래프 (수정됨)

```
Step 1: #9 (모델 정의) ─── criteria.py 분리로 순환 import 방지
            │
            ↓
Step 2: #12a (LLMPort 확장) ─── plan(), evaluate() 추상 메서드 추가
            │
            ↓
Step 3: #10 (EvaluatorService) ─── LLMPort.evaluate() 사용
            │
            ↓
Step 4: #11 (PlannerService) ─── LLMPort.plan() 사용
            │
            ↓
Step 5: #12b (AnthropicAdapter 구현) ─── plan(), evaluate() 실제 구현
            │
            ↓
Step 6: #13 (통합 검증)
```

**변경 이유**: 서비스(Step 3, 4)가 LLMPort의 새 메서드를 사용하므로, Port 확장(Step 2)이 먼저 필요함.

---

## Step 1: Issue #9 — Plan/Task/SuccessCriteria 모델

### 배경
Planner가 생성하고 Evaluator가 검증하는 핵심 모델들. Plan Anchor 패턴의 구조적 기반.

### 파일 생성/수정

| 파일 | 작업 |
|------|------|
| `surfy/domain/models/criteria.py` | **신규** — 순환 import 방지를 위해 분리 |
| `surfy/domain/models/plan.py` | 신규 |
| `surfy/domain/models/task.py` | 수정 |
| `surfy/domain/models/__init__.py` | 수정 |

### 구현 내용

```python
# surfy/domain/models/criteria.py (신규 — 순환 import 방지)
from pydantic import BaseModel


class SuccessCriteria(BaseModel):
    """태스크 완료 조건. Planner가 DOM을 보지 않으므로 추상적 레벨만 사용."""
    url_contains: str | None = None       # URL 패턴 (Planner가 예측 가능)
    text_visible: str | None = None       # 화면에 보여야 할 텍스트
    description: str = ""                 # 자연어 설명 (항상 채움)
```

```python
# surfy/domain/models/task.py (수정)
from pydantic import BaseModel, Field

from surfy.domain.models.criteria import SuccessCriteria


class Task(BaseModel):
    description: str
    success_criteria: SuccessCriteria = Field(default_factory=SuccessCriteria)
```

```python
# surfy/domain/models/plan.py (신규)
from pydantic import BaseModel

from surfy.domain.models.task import Task


class Plan(BaseModel):
    """Plan Anchor 패턴 — 불변 최종 목표(anchor)를 중심으로 rolling wave 계획."""
    anchor: str                     # 불변 최종 목표 (절대 변경 안 됨)
    tasks: list[Task]               # 현재 수립된 태스크들
    anchor_rationale: str           # 왜 이 분해가 anchor 달성에 최적인지
```

**순환 import 해결**:
- `criteria.py` → 독립 (아무것도 import 안 함)
- `task.py` → `criteria.py` import
- `plan.py` → `task.py` import
- 단방향 의존성으로 순환 없음

### 완료 조건
- [ ] 각 모델이 Pydantic `BaseModel`로 정의됨
- [ ] `from surfy.domain.models import Plan, Task, SuccessCriteria` import 가능
- [ ] Pydantic validation 동작
- [ ] 기존 Phase 2 코드와 호환 (success_criteria 기본값으로)

### 테스트
- `tests/test_models.py`에 Plan/Task/SuccessCriteria 검증 추가

---

## Step 2: Issue #12a — LLMPort 확장 (추상 메서드 추가)

### 배경
EvaluatorService와 PlannerService가 사용할 `plan()`, `evaluate()` 메서드를 Port에 먼저 정의.

### 파일 수정

| 파일 | 작업 |
|------|------|
| `surfy/domain/models/result.py` | 수정 (EvalResult 추가) |
| `surfy/domain/models/__init__.py` | 수정 |
| `surfy/domain/ports/llm.py` | 수정 (plan, evaluate 추상 메서드 추가) |

### 구현 내용

```python
# surfy/domain/models/result.py (추가)
class EvalResult(BaseModel):
    """Evaluator의 판정 결과."""
    success: bool
    reason: str
```

```python
# surfy/domain/ports/llm.py (수정)
from abc import ABC, abstractmethod

from surfy.domain.models import ActorOutput, HistoryEntry, PageState, Task
from surfy.domain.models.criteria import SuccessCriteria
from surfy.domain.models.plan import Plan
from surfy.domain.models.result import EvalResult


class LLMPort(ABC):
    @abstractmethod
    async def decide_action(
        self,
        task: Task,
        page_state: PageState,
        history: list[HistoryEntry],
    ) -> ActorOutput:
        """현재 페이지 상태와 히스토리를 기반으로 다음 액션 결정."""
        ...

    @abstractmethod
    async def plan(self, command: str, progress: str) -> Plan:
        """사용자 명령과 진행 상황을 기반으로 Plan 생성."""
        ...

    @abstractmethod
    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
        """SuccessCriteria와 현재 PageState를 기반으로 성공 여부 판정."""
        ...
```

### 완료 조건
- [ ] EvalResult 모델 정의됨
- [ ] LLMPort에 `plan()`, `evaluate()` 추상 메서드 추가됨
- [ ] 기존 `decide_action()` 유지됨

---

## Step 3: Issue #10 — EvaluatorService

### 배경
Evaluator는 Actor가 태스크를 완료했는지 판정. 2단계 평가 전략으로 비용 절감.

**참고**: `BrowserPort.check_text_visible()`은 Phase 1에서 이미 정의되어 있음.

### 파일 생성/수정

| 파일 | 작업 |
|------|------|
| `surfy/domain/services/evaluator.py` | 신규 |
| `surfy/domain/services/__init__.py` | 수정 |

### 구현 내용

```python
# surfy/domain/services/evaluator.py
from surfy.domain.models import PageState, Task
from surfy.domain.models.result import EvalResult
from surfy.domain.ports import BrowserPort, LLMPort


class EvaluatorService:
    def __init__(self, browser: BrowserPort, llm: LLMPort):
        self._browser = browser
        self._llm = llm

    async def evaluate(self, task: Task, page_state: PageState) -> EvalResult:
        criteria = task.success_criteria

        # 1단계: 구조 체크 (비용 없음)
        if criteria.url_contains and criteria.url_contains not in page_state.url:
            return EvalResult(success=False, reason=f"URL에 '{criteria.url_contains}' 없음")

        if criteria.text_visible:
            visible = await self._browser.check_text_visible(criteria.text_visible)
            if not visible:
                return EvalResult(success=False, reason=f"'{criteria.text_visible}' 텍스트 안 보임")

        # 구조 체크 통과 + description만 있으면 → 2단계: LLM 판정
        if criteria.description:
            return await self._llm.evaluate(criteria, page_state)

        return EvalResult(success=True, reason="구조 체크 통과")
```

```python
# surfy/domain/services/__init__.py
from surfy.domain.services.actor import ActorService
from surfy.domain.services.evaluator import EvaluatorService

__all__ = ["ActorService", "EvaluatorService"]
```

### 완료 조건
- [ ] url_contains 매칭 → 즉시 pass/fail 판정 동작
- [ ] text_visible 체크 → BrowserPort.check_text_visible 호출 동작
- [ ] 구조 체크 불충분 시 LLMPort.evaluate 호출 동작

### 테스트
- `tests/test_evaluator.py` — mock BrowserPort/LLMPort로 3가지 경로 테스트:
  1. URL 불일치 → 즉시 실패
  2. 텍스트 불일치 → 즉시 실패
  3. 구조 체크 통과 → LLM 호출

---

## Step 4: Issue #11 — PlannerService

### 배경
Planner는 사용자 명령을 태스크로 분해하는 전략 컴포넌트. DOM을 보지 않고 추상적 레벨에서만 작업.

### 파일 생성/수정

| 파일 | 작업 |
|------|------|
| `surfy/domain/services/planner.py` | 신규 |
| `surfy/domain/services/__init__.py` | 수정 |

### 구현 내용

```python
# surfy/domain/services/planner.py
from surfy.domain.models import Task
from surfy.domain.models.plan import Plan
from surfy.domain.ports import LLMPort


class PlannerService:
    def __init__(self, llm: LLMPort):
        self._llm = llm

    async def create_plan(self, command: str) -> Plan:
        """첫 호출: anchor 설정 + 첫 1~2 태스크 생성."""
        return await self._llm.plan(command, progress="")

    async def next_tasks(self, plan: Plan, completed_tasks: list[Task]) -> Plan:
        """이후 호출: anchor 유지, 진행 상황 기반으로 다음 태스크 생성 (rolling wave)."""
        progress = self._summarize_progress(completed_tasks)
        new_plan = await self._llm.plan(plan.anchor, progress)
        new_plan.anchor = plan.anchor  # anchor는 절대 변경 안 됨
        return new_plan

    async def replan(self, plan: Plan, failed_task: Task, reason: str) -> Plan:
        """Replan: 실패 구간만 재계획, anchor와 성공한 태스크 보존."""
        progress = f"실패한 태스크: {failed_task.description}\n사유: {reason}"
        new_plan = await self._llm.plan(plan.anchor, progress)
        new_plan.anchor = plan.anchor  # anchor는 절대 변경 안 됨
        return new_plan

    def _summarize_progress(self, completed_tasks: list[Task]) -> str:
        if not completed_tasks:
            return ""
        return "완료된 태스크:\n" + "\n".join(
            f"- {task.description}" for task in completed_tasks
        )
```

```python
# surfy/domain/services/__init__.py (최종)
from surfy.domain.services.actor import ActorService
from surfy.domain.services.evaluator import EvaluatorService
from surfy.domain.services.planner import PlannerService

__all__ = ["ActorService", "EvaluatorService", "PlannerService"]
```

### 완료 조건
- [ ] `create_plan` — 사용자 명령으로부터 Plan(anchor + tasks) 생성
- [ ] `next_tasks` — 기존 anchor 유지하면서 다음 태스크 추가
- [ ] `replan` — 실패 시 해당 구간만 재계획
- [ ] anchor가 어떤 경우에도 변경되지 않음을 검증

### 테스트
- `tests/test_planner.py` — mock LLMPort로:
  1. create_plan: anchor 설정 검증
  2. next_tasks: anchor 불변 검증
  3. replan: 실패 정보 전달 검증

---

## Step 5: Issue #12b — AnthropicAdapter 구현

### 배경
Step 2에서 정의한 `plan()`, `evaluate()` 추상 메서드를 실제로 구현.

### 파일 생성/수정

| 파일 | 작업 |
|------|------|
| `surfy/adapters/llm/anthropic_adapter.py` | 수정 |
| `surfy/prompts/planner.prompty` | 신규 |
| `surfy/prompts/evaluator.prompty` | 신규 |

### 구현 내용

```python
# surfy/adapters/llm/anthropic_adapter.py (추가)
async def plan(self, command: str, progress: str) -> Plan:
    template_str = self._plan_prompt_template.replace("{{", "${").replace("}}", "}")
    template = Template(template_str)
    prompt = template.safe_substitute(command=command, progress=progress or "(없음)")

    structured_model = self._model.with_structured_output(Plan)
    result = await structured_model.ainvoke([HumanMessage(content=prompt)])
    return result if isinstance(result, Plan) else Plan(**result)

async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult:
    template_str = self._eval_prompt_template.replace("{{", "${").replace("}}", "}")
    template = Template(template_str)
    prompt = template.safe_substitute(
        description=criteria.description,
        url=page_state.url,
        dom_text=page_state.dom_text[:5000],  # 토큰 제한
    )

    # vision 지원
    if self._use_vision and page_state.screenshot:
        messages = [HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{page_state.screenshot}"}},
        ])]
    else:
        messages = [HumanMessage(content=prompt)]

    structured_model = self._model.with_structured_output(EvalResult)
    result = await structured_model.ainvoke(messages)
    return result if isinstance(result, EvalResult) else EvalResult(**result)
```

### 프롬프트 파일

**planner.prompty:**
```yaml
---
name: planner
description: Generate a plan for the given command
---
system:
You are a task planner for a web browsing agent.

Given a user command, create a plan with:
1. anchor: The ultimate goal (immutable, in Korean if the command is in Korean)
2. tasks: 1-2 concrete, actionable browser tasks to achieve the goal
3. anchor_rationale: Why this decomposition is optimal for achieving the anchor

Each task must have:
- description: What the browser agent should do
- success_criteria: How to verify completion (url_contains, text_visible, or description)

User command: {{command}}

Progress so far: {{progress}}

IMPORTANT:
- Keep tasks atomic and achievable in a single browser session
- Each task should be independently verifiable
- Use Korean for descriptions if the command is in Korean
```

**evaluator.prompty:**
```yaml
---
name: evaluator
description: Evaluate if a task was completed successfully
---
system:
You are an evaluator for a web browsing agent.

Determine if the task was completed successfully based on:
- Success criteria description: {{description}}
- Current URL: {{url}}
- Page content (truncated): {{dom_text}}

Analyze the page content carefully and determine if the success criteria is met.

Return:
- success: true if the criteria is clearly met, false otherwise
- reason: Brief explanation of why (in Korean if criteria is in Korean)

Be strict but fair. If the page shows clear evidence of task completion, mark as success.
```

### 완료 조건
- [ ] `plan()` 호출 시 `Plan` 객체 정상 반환
- [ ] `evaluate()` 호출 시 `EvalResult` 객체 정상 반환
- [ ] LLMPort ABC의 모든 메서드가 구현 완료됨

---

## Step 6: Issue #13 — 통합 검증

### 배경
Phase 3의 모든 컴포넌트(Planner + Actor + Evaluator)가 실제로 연결되어 동작하는지 검증.

### 파일 생성

| 파일 | 작업 |
|------|------|
| `scripts/test_phase3.py` | 신규 |

### 구현 내용

```python
# scripts/test_phase3.py
"""
Phase 3 통합 검증 — Planner → Actor → Evaluator 수동 연결 테스트

사용법:
1. Chrome을 --remote-debugging-port=9222로 실행
2. ANTHROPIC_API_KEY 환경변수 설정
3. python scripts/test_phase3.py
"""
import asyncio
import logging

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.llm import AnthropicAdapter
from surfy.domain.services import ActorService, EvaluatorService, PlannerService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CDP_URL = "http://localhost:9222"
MODEL_NAME = "claude-sonnet-4-20250514"


async def main():
    # 1. 어댑터 초기화 (factory method 사용)
    browser = await BrowserUseAdapter.create(CDP_URL)

    llm = AnthropicAdapter(use_vision=True, model_name=MODEL_NAME)

    # 2. 서비스 초기화
    planner = PlannerService(llm)
    actor = ActorService(browser, llm)
    evaluator = EvaluatorService(browser, llm)

    # 3. 테스트 명령
    command = "네이버에서 날씨 검색 후 내일 기온 확인"

    try:
        # 4. Planner: Plan 생성
        logger.info("=== Planner: Creating plan ===")
        plan = await planner.create_plan(command)
        logger.info(f"Anchor: {plan.anchor}")
        logger.info(f"Tasks: {[t.description for t in plan.tasks]}")
        logger.info(f"Rationale: {plan.anchor_rationale}")

        # 5. 각 Task 실행 및 평가
        for i, task in enumerate(plan.tasks):
            logger.info(f"\n=== Task {i+1}: {task.description} ===")

            # Actor 실행
            step_result = await actor.execute_task(task)
            logger.info(f"Actor result: {step_result.success} - {step_result.message}")

            if not step_result.success:
                logger.error(f"Task failed: {step_result.message}")
                break

            # Evaluator 판정 — Actor 완료 직후 페이지 상태 사용
            page_state = step_result.page_state or await browser.get_page_state()
            eval_result = await evaluator.evaluate(task, page_state)
            logger.info(f"Evaluator result: {eval_result.success} - {eval_result.reason}")

            if not eval_result.success:
                logger.warning(f"Task not verified: {eval_result.reason}")
                # 여기서 replan 가능

        logger.info("\n=== Phase 3 Integration Test Complete ===")

    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
```

### 완료 조건
- [ ] Planner가 태스크를 2개 이상으로 분해
- [ ] Actor가 각 태스크를 순차 실행
- [ ] Evaluator가 각 태스크 완료 여부를 판정
- [ ] 전체 흐름이 끊기지 않고 동작 (실패해도 로그로 확인 가능)

---

## 파일별 작업 요약

| 파일 | 작업 | Step |
|------|------|------|
| `domain/models/criteria.py` | **신규** | 1 |
| `domain/models/plan.py` | 신규 | 1 |
| `domain/models/task.py` | 수정 | 1 |
| `domain/models/result.py` | 수정 | 2 |
| `domain/models/__init__.py` | 수정 | 1, 2 |
| `domain/ports/llm.py` | 수정 | 2 |
| `domain/services/evaluator.py` | 신규 | 3 |
| `domain/services/planner.py` | 신규 | 4 |
| `domain/services/__init__.py` | 수정 | 3, 4 |
| `adapters/llm/anthropic_adapter.py` | 수정 | 5 |
| `prompts/planner.prompty` | 신규 | 5 |
| `prompts/evaluator.prompty` | 신규 | 5 |
| `tests/test_models.py` | 수정 | 1 |
| `tests/test_evaluator.py` | 신규 | 3 |
| `tests/test_planner.py` | 신규 | 4 |
| `scripts/test_phase3.py` | 신규 | 6 |

---

## 기존 코드 참고사항

### 이미 존재하는 것들 (구현 불필요)
- `BrowserPort.check_text_visible()` — Phase 1에서 이미 정의됨 (`browser.py:14`)
- `BrowserUseAdapter.connect()` — Phase 1에서 이미 구현됨

### 주의사항
1. **기존 Task 모델 호환성**: `success_criteria`에 기본값 제공하여 Phase 2 코드가 깨지지 않도록
2. **순환 import 방지**: `criteria.py` 분리로 해결 (이 문서의 Step 1 참조)
3. **LLMPort 하위 호환**: `plan()`, `evaluate()` 추가 시 기존 `decide_action()`은 그대로 유지

---

## 예상 소요 시간

| Step | 작업 | 예상 시간 |
|------|------|----------|
| 1 | 모델 정의 (criteria.py 분리 포함) | 1시간 |
| 2 | LLMPort 확장 + EvalResult | 0.5시간 |
| 3 | EvaluatorService | 1.5시간 |
| 4 | PlannerService | 1시간 |
| 5 | AnthropicAdapter 구현 | 2시간 |
| 6 | 통합 검증 | 1.5시간 |
| - | 테스트 작성 | 2시간 |
| **Total** | | **~9.5시간** |

---

## 리뷰 피드백 반영 내역

| 피드백 | 해결 방법 |
|--------|----------|
| 순환 import 위험 (`plan.py ↔ task.py`) | `criteria.py` 분리하여 단방향 의존성 확보 |
| Step 순서 문제 (Port 확장이 서비스보다 뒤) | Step 2로 Port 확장 이동, 6단계로 재구성 |
| `check_text_visible` 이미 존재 | "기존 코드 참고사항" 섹션 추가 |
| 통합 스크립트에서 page_state 획득 시점 | `step_result.page_state` 우선 사용하도록 수정 |
