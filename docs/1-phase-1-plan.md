# Phase 1 구현 계획 — 기반 (브라우저 연결 + 화면 캡처)

## Context

surfy는 Hexagonal Architecture + Hierarchical Agent 구조로 재설계 중이다. 현재 디렉토리 구조만 잡혀 있고(`__init__.py` stub만 존재), 모든 구현이 비어 있다. Phase 1에서는 도메인 모델과 브라우저 연결 기반을 구축하여 이후 Phase(Actor, Planner 등)의 토대를 만든다.

browser-use v0.11.9 API 조사 결과, 핵심 래핑 대상은:
- `BrowserSession(cdp_url=...)` → CDP 연결 (BrowserConfig 없음, 생성자에서 직접 받음)
- `BrowserSession.get_browser_state_summary()` → URL, title, DOM, screenshot 한 번에 획득
- `SerializedDOMState.llm_representation()` → LLM용 DOM 텍스트
- `SerializedDOMState.selector_map` → `dict[int, EnhancedDOMTreeNode]` (backend_node_id 포함)
- `Page.goto()`, `Element.click()`, `Element.fill()` → 액션 실행

## 선행 작업

- [ ] `pyproject.toml`의 `browser-use>=0.2`를 `browser-use>=0.11,<1.0`으로 변경 (v0.11.9 API 기준 설계)

## 구현 순서

### Step 1: 도메인 모델 정의 (Issue #1) — `good-first-issue`

**파일**: `surfy/domain/models/action.py`, `screen.py`, `result.py`, `__init__.py`

```python
# action.py
from enum import Enum
from pydantic import BaseModel

class ActionType(str, Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    SCROLL_DOWN = "SCROLL_DOWN"
    SCROLL_UP = "SCROLL_UP"
    GO_TO_URL = "GO_TO_URL"
    SEND_KEYS = "SEND_KEYS"    # Enter, Tab, Escape 등 키보드 입력
    GO_BACK = "GO_BACK"        # 브라우저 뒤로가기
    DONE = "DONE"
    STUCK = "STUCK"

class BrowserAction(BaseModel):
    action_type: ActionType
    target_id: int | None = None    # selector_map index
    value: str | None = None        # TYPE시 입력값, GO_TO_URL시 URL
```

```python
# screen.py
from pydantic import BaseModel

class PageState(BaseModel):
    url: str
    title: str
    dom_text: str
    screenshot: str | None = None   # base64 PNG (bytes 아닌 str — browser-use가 base64 str 반환)
```

```python
# result.py
from __future__ import annotations
from pydantic import BaseModel
from surfy.domain.models.screen import PageState

class StepResult(BaseModel):
    success: bool
    message: str
    page_state: PageState | None = None
```

```python
# __init__.py
from surfy.domain.models.action import ActionType, BrowserAction
from surfy.domain.models.screen import PageState
from surfy.domain.models.result import StepResult
```

**완료 조건**:
```bash
uv run python -c "from surfy.domain.models import PageState, BrowserAction, ActionType, StepResult; print('OK')"
```

### Step 2: BrowserPort ABC 정의 (Issue #2) — `good-first-issue`

**파일**: `surfy/domain/ports/browser.py`, `__init__.py`

**의존**: Issue #1

```python
# browser.py
from abc import ABC, abstractmethod
from surfy.domain.models import PageState, BrowserAction, StepResult

class BrowserPort(ABC):
    @abstractmethod
    async def connect(self, cdp_url: str) -> None: ...

    @abstractmethod
    async def get_page_state(self) -> PageState: ...

    @abstractmethod
    async def execute_action(self, action: BrowserAction) -> StepResult: ...

    @abstractmethod
    async def check_text_visible(self, text: str) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...
```

```python
# __init__.py
from surfy.domain.ports.browser import BrowserPort
```

**완료 조건**:
```bash
uv run python -c "from surfy.domain.ports import BrowserPort; print('OK')"
```

### Step 3-A: BrowserUseAdapter — connect + get_page_state (Issue #3)

**파일**: `surfy/adapters/browser/browser_use_adapter.py`

**의존**: Issue #1, #2

핵심 설계 결정:
- `BrowserSession`을 직접 래핑 (Agent 클래스는 사용하지 않음 — 우리가 자체 Actor 만들 예정)
- `BrowserSession(cdp_url=cdp_url)` 로 생성 (~~`BrowserConfig` 미사용~~ — 존재하지 않는 클래스)
- `get_page_state()`: `BrowserSession.get_browser_state_summary()` 호출 → PageState 변환
- 최신 `BrowserStateSummary`를 캐시하여 selector_map 재활용

```python
import logging
from browser_use import BrowserSession
from browser_use.browser.views import BrowserStateSummary
from surfy.domain.models import PageState, BrowserAction, StepResult, ActionType
from surfy.domain.ports import BrowserPort

logger = logging.getLogger(__name__)

class BrowserUseAdapter(BrowserPort):
    def __init__(self):
        self._session: BrowserSession | None = None
        self._last_state: BrowserStateSummary | None = None

    async def connect(self, cdp_url: str) -> None:
        self._session = BrowserSession(cdp_url=cdp_url)
        await self._session.start()
        logger.info("CDP 연결 완료: %s", cdp_url)

    async def get_page_state(self) -> PageState:
        summary = await self._session.get_browser_state_summary()
        self._last_state = summary  # selector_map 캐시
        return PageState(
            url=summary.url,
            title=summary.title,
            dom_text=summary.dom_state.llm_representation(),
            screenshot=summary.screenshot,
        )

    async def execute_action(self, action: BrowserAction) -> StepResult:
        # Step 3-B에서 구현
        raise NotImplementedError

    async def check_text_visible(self, text: str) -> bool:
        if self._last_state is None:
            await self.get_page_state()
        return text in self._last_state.dom_state.llm_representation()

    async def close(self) -> None:
        if self._session:
            await self._session.stop()
```

**완료 조건**:
1. Chrome을 `--remote-debugging-port=9222`로 실행
2. 아래 스크립트로 연결 + 상태 조회 성공:
```python
import asyncio
from surfy.adapters.browser.browser_use_adapter import BrowserUseAdapter

async def main():
    adapter = BrowserUseAdapter()
    await adapter.connect("http://localhost:9222")
    state = await adapter.get_page_state()
    print(f"URL: {state.url}")
    print(f"Title: {state.title}")
    print(f"DOM length: {len(state.dom_text)}")
    print(f"Screenshot: {'있음' if state.screenshot else '없음'}")
    await adapter.close()

asyncio.run(main())
```

### Step 3-B: BrowserUseAdapter — execute_action (Issue #4)

**파일**: `surfy/adapters/browser/browser_use_adapter.py` (Step 3-A에 이어서 추가)

**의존**: Issue #3

```python
from browser_use.actor.element import Element

# BrowserUseAdapter 클래스에 추가:

    async def execute_action(self, action: BrowserAction) -> StepResult:
        if action.action_type in (ActionType.DONE, ActionType.STUCK):
            return StepResult(success=True, message=f"{action.action_type.value}")

        try:
            page = await self._session.get_current_page()
            if page is None:
                return StepResult(success=False, message="활성 페이지 없음")

            match action.action_type:
                case ActionType.GO_TO_URL:
                    await page.goto(action.value)
                case ActionType.CLICK:
                    element = self._resolve_element(action.target_id)
                    await element.click()
                case ActionType.TYPE:
                    element = self._resolve_element(action.target_id)
                    await element.fill(action.value)
                case ActionType.SCROLL_DOWN:
                    await page.evaluate("window.scrollBy(0, 500)")
                case ActionType.SCROLL_UP:
                    await page.evaluate("window.scrollBy(0, -500)")
                case ActionType.SEND_KEYS:
                    await page.press(action.value)  # "Enter", "Tab", "Escape" 등
                case ActionType.GO_BACK:
                    await page.go_back()

            new_state = await self.get_page_state()
            return StepResult(success=True, message=f"{action.action_type.value} 완료", page_state=new_state)
        except Exception as e:
            logger.exception("액션 실행 실패: %s", action)
            return StepResult(success=False, message=str(e))

    def _resolve_element(self, target_id: int) -> Element:
        """selector_map index → browser-use Element 변환.

        변환 체인: target_id → selector_map[target_id] → EnhancedDOMTreeNode → backend_node_id → Element

        주의: get_page_state()를 먼저 호출하여 _last_state가 존재해야 함.
        """
        if self._last_state is None:
            raise RuntimeError("get_page_state()를 먼저 호출해야 합니다")
        if target_id is None:
            raise ValueError("CLICK/TYPE 액션에는 target_id가 필요합니다")

        node = self._last_state.dom_state.selector_map[target_id]
        return Element(
            browser_session=self._session,
            backend_node_id=node.backend_node_id,
            session_id=node.session_id,
        )
```

**변경점 (기존 대비)**:
- `BrowserConfig` 제거 → `BrowserSession(cdp_url=...)` 직접 사용
- `get_current_page()` None 체크 추가
- `_last_state` None 체크 추가
- `target_id` None 체크 추가
- try/except로 `StepResult(success=False)` 반환
- DONE/STUCK을 match 전에 early return 처리
- SEND_KEYS/GO_BACK에서 중복 `get_current_page()` 호출 제거
- `_resolve_element`은 비동기 아님 (async 불필요 — 캐시된 데이터 조회만)

**완료 조건**:
1. Chrome을 `--remote-debugging-port=9222`로 실행
2. `scripts/test_phase1.py` (Step 4)로 GO_TO_URL → CLICK/TYPE 검증

### Step 4: 도메인 모델 단위 테스트 (Issue #5) — `good-first-issue`

**파일**: `tests/test_models.py`

**의존**: Issue #1

```python
import pytest
from surfy.domain.models import ActionType, BrowserAction, PageState, StepResult

def test_browser_action_defaults():
    action = BrowserAction(action_type=ActionType.SCROLL_DOWN)
    assert action.target_id is None
    assert action.value is None

def test_browser_action_click():
    action = BrowserAction(action_type=ActionType.CLICK, target_id=5)
    assert action.target_id == 5

def test_page_state_required_fields():
    state = PageState(url="https://example.com", title="Example", dom_text="<body>hi</body>")
    assert state.screenshot is None

def test_step_result_success():
    result = StepResult(success=True, message="OK")
    assert result.page_state is None

def test_step_result_with_page_state():
    state = PageState(url="https://example.com", title="Example", dom_text="dom")
    result = StepResult(success=True, message="OK", page_state=state)
    assert result.page_state.url == "https://example.com"

def test_invalid_action_type():
    with pytest.raises(ValueError):
        BrowserAction(action_type="INVALID")
```

**완료 조건**:
```bash
uv run pytest tests/test_models.py -v
```

### Step 5: 통합 검증 스크립트 (Issue #6)

**파일**: `scripts/test_phase1.py`

**의존**: Issue #3, #4

```python
"""Phase 1 통합 검증 — Chrome CDP 연결 + DOM + screenshot + 액션 실행.

사전 조건: Chrome을 --remote-debugging-port=9222 로 실행해야 함.
"""
import asyncio
import base64
import logging
from pathlib import Path

from surfy.adapters.browser.browser_use_adapter import BrowserUseAdapter
from surfy.domain.models import ActionType, BrowserAction

logging.basicConfig(level=logging.INFO)

async def main():
    adapter = BrowserUseAdapter()
    await adapter.connect("http://localhost:9222")

    try:
        # 1. 페이지 이동
        result = await adapter.execute_action(
            BrowserAction(action_type=ActionType.GO_TO_URL, value="https://www.google.com")
        )
        print(f"[GO_TO_URL] success={result.success}, message={result.message}")

        # 2. 상태 확인
        state = await adapter.get_page_state()
        print(f"URL: {state.url}")
        print(f"Title: {state.title}")
        print(f"DOM (first 500 chars): {state.dom_text[:500]}")

        # 3. screenshot 저장
        if state.screenshot:
            out = Path("screenshot.png")
            out.write_bytes(base64.b64decode(state.screenshot))
            print(f"Screenshot 저장: {out.resolve()}")

        # 4. 텍스트 가시성 체크
        print(f"'Google' visible: {await adapter.check_text_visible('Google')}")
    finally:
        await adapter.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**완료 조건**:
```bash
# Chrome 실행 (별도 터미널)
google-chrome --remote-debugging-port=9222

# 검증 실행
uv run python scripts/test_phase1.py
```
- URL, Title, DOM 출력 확인
- `screenshot.png` 파일 생성 확인
- `'Google' visible: True` 출력 확인

## Issue 의존 관계

```
Issue #1 (도메인 모델)
  ├─→ Issue #2 (BrowserPort ABC)
  │     └─→ Issue #3 (Adapter: connect + get_page_state)
  │           └─→ Issue #4 (Adapter: execute_action)
  │                 └─→ Issue #6 (통합 검증 스크립트)
  └─→ Issue #5 (도메인 모델 단위 테스트)
```

## Issue 할당 가이드

| Issue | 난이도 | 라벨 | 적합 담당자 |
|-------|--------|------|------------|
| #1 도메인 모델 | 쉬움 | `good-first-issue`, `phase-1` | 주니어 누구나 |
| #2 BrowserPort ABC | 쉬움 | `good-first-issue`, `phase-1` | 주니어 누구나 |
| #3 Adapter connect | 중간 | `phase-1` | Lead 또는 시니어 주니어 |
| #4 Adapter execute | 어려움 | `phase-1` | Lead |
| #5 모델 테스트 | 쉬움 | `good-first-issue`, `phase-1` | 주니어 누구나 |
| #6 통합 검증 | 중간 | `phase-1` | Issue #3, #4 담당자 |

## 검증 요약

| 단계 | 명령어 | 확인 사항 |
|------|--------|----------|
| 모델 import | `uv run python -c "from surfy.domain.models import PageState, BrowserAction, ActionType, StepResult; print('OK')"` | OK 출력 |
| Port import | `uv run python -c "from surfy.domain.ports import BrowserPort; print('OK')"` | OK 출력 |
| 단위 테스트 | `uv run pytest tests/test_models.py -v` | 전체 통과 |
| 통합 검증 | `uv run python scripts/test_phase1.py` | CDP 연결 + DOM + screenshot |

## _resolve_element 조사 결과

browser-use 내부 코드 조사 완료. element resolve 체인:

```
selector_map[index] → EnhancedDOMTreeNode → backend_node_id → CDP 명령
```

- **CSS selector 미사용** — 모든 조작은 `backend_node_id`로 수행
- **Element 클래스** (`browser_use/actor/element.py`): `backend_node_id`를 받아 CDP로 click/fill 처리
  - `Element(browser_session, backend_node_id, session_id)` 로 생성
  - `click()`: `DOM.getContentQuads(backendNodeId)` → 좌표 계산 → `Input.dispatchMouseEvent` (JS fallback 포함)
  - `fill()`: `DOM.resolveNode(backendNodeId)` → objectId → `Runtime.callFunctionOn`으로 텍스트 입력
- **Event Bus 대안**: `ClickElementEvent(node=node)` dispatch도 가능하지만, `Element` 클래스 직접 사용이 더 단순함

**결론**: `Element(session, backend_node_id, session_id)` 직접 생성하여 `click()`/`fill()` 호출. browser-use가 CDP 복잡성(좌표 계산, fallback, iframe 등)을 전부 처리해줌.