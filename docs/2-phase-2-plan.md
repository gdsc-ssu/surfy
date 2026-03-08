# Phase 2 계획: Actor (핵심 루프)

## 현재 상태

**Phase 1 완료:**
- `domain/ports/browser.py` - BrowserPort ABC
- `adapters/browser/browser_use_adapter.py` - CDP 연결, get_page_state, execute_action
- `domain/models/` - PageState, BrowserAction, ActionType, StepResult

## Phase 2 목표

1. `domain/models/task.py` — Task 모델 정의
2. `domain/models/actor.py` — ActorOutput 모델 정의
3. `domain/ports/llm.py` — LLMPort ABC 정의
4. `adapters/llm/anthropic_adapter.py` — decide_action 구현
5. `domain/services/actor.py` — ActorService ReAct while loop 구현
6. **검증**: 단순 태스크 ("google.com에서 'hello' 검색") 실제 Chrome에서 수동 실행

---

## 결정 사항

| 항목 | 결정 |
|------|------|
| Task 모델 위치 | `domain/models/task.py` (신규) |
| ActorOutput 위치 | `domain/models/actor.py` (신규) |
| Screenshot 전달 | A/B 테스트용 `use_vision: bool` 플래그 (기본값: False) |
| 히스토리 압축 | 5개 초과 시 앞부분 압축 + 최근 5개 상세 |
| 테스트 환경 | 실제 Chrome 사용 |
| Computer Use API | Phase 2에서 고려하지 않음 |

---

## GitHub Issues

| Issue | 제목 | 난이도 | 라벨 |
|-------|------|--------|------|
| [#6](../../issues/6) | ActorOutput 모델 + ActorService ReAct 루프 구현 | 높음 | `phase-2` |
| [#5](../../issues/5) | LLMPort ABC 정의 | 낮음 | `phase-2`, `good-first-issue` |
| [#7](../../issues/7) | AnthropicAdapter — decide_action 구현 | 중간 | `phase-2` |
| [#8](../../issues/8) | 통합 검증 — Actor 단독 실행 (Google 검색) | 중간 | `phase-2` |

---

## Issue 상세

### Issue #6: Task/ActorOutput 모델 + ActorService 구현

**파일 1**: `surfy/domain/models/task.py` (신규)

```python
from pydantic import BaseModel


class Task(BaseModel):
    description: str
    # success_criteria는 Phase 3에서 추가
```

**파일 2**: `surfy/domain/models/actor.py` (신규)

```python
from pydantic import BaseModel
from surfy.domain.models.action import ActionType, BrowserAction


class ActorOutput(BaseModel):
    thinking: str           # 현재 상황 분석
    action_type: ActionType
    target_id: int | None = None
    value: str | None = None

    def to_browser_action(self) -> BrowserAction:
        return BrowserAction(
            action_type=self.action_type,
            target_id=self.target_id,
            value=self.value,
        )
```

**파일 3**: `surfy/domain/services/actor.py` (신규)

```python
import logging
from surfy.domain.models import Task, ActorOutput, ActionType, StepResult
from surfy.domain.ports import BrowserPort, LLMPort

logger = logging.getLogger(__name__)


class ActorService:
    def __init__(self, browser: BrowserPort, llm: LLMPort):
        self._browser = browser
        self._llm = llm

    async def execute_task(self, task: Task, max_steps: int = 15) -> StepResult:
        history: list[tuple[ActorOutput, StepResult]] = []

        for step in range(max_steps):
            page_state = await self._browser.get_page_state()
            output = await self._llm.decide_action(task, page_state, history)
            
            logger.info(
                "Step %d: %s (target=%s, value=%s)",
                step + 1,
                output.action_type.value,
                output.target_id,
                output.value,
            )

            action = output.to_browser_action()
            result = await self._browser.execute_action(action)
            history.append((output, result))

            if output.action_type in (ActionType.DONE, ActionType.STUCK):
                break

        return result
```

**완료 조건:**
- [ ] Task 모델 정의됨
- [ ] ActorOutput 모델 정의됨
- [ ] `surfy/domain/models/__init__.py`에 `Task`, `ActorOutput` export 추가
- [ ] `surfy/domain/services/__init__.py`에 `ActorService` export 추가
- [ ] `from surfy.domain.models import Task, ActorOutput` import 가능
- [ ] `from surfy.domain.services import ActorService` import 가능
- [ ] ActorService가 BrowserPort + LLMPort를 주입받아 인스턴스화 가능
- [ ] mock LLM/Browser로 while loop 정상 동작 (DONE 반환 시 종료)
- [ ] max_steps 초과 시 정상 종료

---

### Issue #5: LLMPort ABC 정의

**파일**: `surfy/domain/ports/llm.py` (신규)

```python
from abc import ABC, abstractmethod
from surfy.domain.models import Task, ActorOutput, PageState, StepResult


class LLMPort(ABC):
    @abstractmethod
    async def decide_action(
        self,
        task: Task,
        page_state: PageState,
        history: list[tuple[ActorOutput, StepResult]],
    ) -> ActorOutput:
        """현재 페이지 상태와 히스토리를 기반으로 다음 액션 결정."""
        ...

    # plan(), evaluate()는 Phase 3에서 추가
```

**완료 조건:**
- [ ] ABC class 정의 완료
- [ ] 모든 메서드에 타입 힌트 포함
- [ ] `surfy/domain/ports/__init__.py`에 `LLMPort` export 추가
- [ ] `from surfy.domain.ports import LLMPort` import 가능

---

### Issue #7: AnthropicAdapter — decide_action 구현

**파일**: `surfy/adapters/llm/anthropic_adapter.py` (신규)

**핵심 구현:**
- `langchain-anthropic`의 `ChatAnthropic` + `with_structured_output()` 사용
- `use_vision: bool` 파라미터로 screenshot 전달 여부 선택 (A/B 테스트용)
- 모델: `claude-sonnet-4-5-20250929`

**프롬프트 구조:**
```
You are a browser automation agent executing a single task.

Task: {task.description}

Current page:
- URL: {page_state.url}
- Title: {page_state.title}

Interactive elements (DOM):
{page_state.dom_text}

Recent actions:
{formatted_history}

Available actions:
- CLICK: Click element by target_id
- TYPE: Type text into element (target_id + value)
- SCROLL_DOWN / SCROLL_UP: Scroll the page
- GO_TO_URL: Navigate to URL (value)
- SEND_KEYS: Send keyboard key (value: "Enter", "Tab", etc.)
- GO_BACK: Go back in browser history
- DONE: Task completed successfully
- STUCK: Cannot proceed, need help

Respond with your thinking and exactly ONE action.
```

**Vision (screenshot) 지원:**
```python
from langchain.messages import HumanMessage

# use_vision=True일 때
if self._use_vision and page_state.screenshot:
    messages = [
        HumanMessage(content=[
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{page_state.screenshot}"},
            },
        ])
    ]
else:
    messages = [HumanMessage(content=prompt)]
```

**히스토리 압축 로직:**
```python
def _format_history(self, history: list[tuple[ActorOutput, StepResult]]) -> str:
    if len(history) <= 5:
        return "\n".join([
            f"Step {i+1}: {h[0].action_type.value}({h[0].target_id or h[0].value or ''}) → {h[1].message}"
            for i, h in enumerate(history)
        ])
    
    # 5개 초과: 앞부분 압축 + 최근 5개 상세
    old_actions = [h[0].action_type.value for h in history[:-5]]
    old_summary = f"[Earlier {len(old_actions)} steps: {' → '.join(old_actions)}]"
    
    recent = history[-5:]
    recent_text = "\n".join([
        f"Step {len(history)-5+i+1}: {h[0].action_type.value}({h[0].target_id or h[0].value or ''}) → {h[1].message}"
        for i, h in enumerate(recent)
    ])
    return f"{old_summary}\n\n{recent_text}"
```

**완료 조건:**
- [ ] Anthropic API 호출 성공 (ANTHROPIC_API_KEY 환경변수 필요)
- [ ] `ActorOutput` 형식으로 파싱 성공
- [ ] `use_vision=False`: DOM text만 전송
- [ ] `use_vision=True`: DOM text + screenshot 전송
- [ ] `surfy/adapters/llm/__init__.py`에 `AnthropicAdapter` export 추가
- [ ] `from surfy.adapters.llm import AnthropicAdapter` import 가능

---

### Issue #8: 통합 검증 — Actor 단독 실행 (Google 검색)

**파일**: `scripts/test_phase2.py` (신규)

> **참고**: `scripts/` 디렉토리가 없으므로 먼저 생성 필요

**검증 시나리오**: "google.com에서 'hello' 검색"

```python
import asyncio
import logging

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.llm import AnthropicAdapter
from surfy.domain.models import Task
from surfy.domain.services import ActorService

logging.basicConfig(level=logging.INFO)


async def main():
    # 1. Chrome CDP 연결
    browser = await BrowserUseAdapter.create("http://localhost:9222")
    
    try:
        # 2. Anthropic API 연결
        llm = AnthropicAdapter(use_vision=False)
        
        # 3. Actor 생성
        actor = ActorService(browser=browser, llm=llm)
        
        # 4. Task 정의 및 실행
        task = Task(description="google.com에 접속해서 'hello'를 검색하세요")
        result = await actor.execute_task(task, max_steps=10)
        
        # 5. 결과 확인
        page_state = await browser.get_page_state()
        print(f"Final URL: {page_state.url}")
        print(f"Result: {result}")
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
```

**실행 방법:**
```bash
# 1. Chrome을 CDP 모드로 실행
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# 2. 테스트 스크립트 실행
ANTHROPIC_API_KEY=sk-... uv run python scripts/test_phase2.py
```

**완료 조건:**
- [ ] Actor가 google.com으로 이동
- [ ] 검색창을 찾아 클릭
- [ ] 'hello' 입력 후 검색 실행
- [ ] 검색 결과 페이지 도달 (DONE 반환)
- [ ] 10스텝 이내 완료

---

## 의존성 그래프

```
#6 (Task, ActorOutput, ActorService) ─┬─> #5 (LLMPort) ─> #7 (AnthropicAdapter) ─┐
                                      │                                           │
                                      └───────────────────────────────────────────┴─> #8 (통합 검증)
```

**구현 순서:**
1. Issue #6: Task, ActorOutput 모델 + ActorService (의존성 없음)
2. Issue #5: LLMPort ABC (#6 의존)
3. Issue #7: AnthropicAdapter (#5, #6 의존)
4. Issue #8: 통합 검증 (#5, #6, #7 의존)

---

## 담당자 배정 제안

| Issue | 난이도 | 추천 담당자 |
|-------|--------|------------|
| #6 Task/ActorOutput/ActorService | 높음 | @kimseoungyun (+ @rover0811 리뷰) |
| #5 LLMPort | 낮음 | @hsung0714-bot 또는 @SeoYeongBaek |
| #7 AnthropicAdapter | 중간 | @kimseoungyun |
| #8 통합 검증 | 중간 | @rover0811 |
