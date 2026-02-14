# Surfy Architecture Redesign — Hexagonal + Hierarchical Agent

## Context

현재 surfy는 README의 비전(Macro Planner → Micro Planner → CDP Executor → Reviewer)을 코드 구조로 잡았지만, 모든 핵심 로직이 TODO stub이고, Micro Planner의 multi-action 사전 계획 방식은 SPA/동적 웹에서 작동하지 않는 근본적 설계 결함이 있다.

**재설계 목표:**
- Hexagonal Architecture로 관심사 분리
- browser-use의 검증된 DOM 처리를 그대로 활용
- Hierarchical Agent (Planner + Actor + Evaluator)로 태스크 성공률 최적화
- WebAnchor 논문의 Plan Anchor 개념 적용 — 첫 계획 품질이 전체 성공률을 결정
- 기존 코드 전부 교체 (clean slate)

## 핵심 설계 결정

### 1. Hierarchical 3-Component Architecture

```
User Command
    ↓
┌─ LangGraph Outer Loop ──────────────────────┐
│                                              │
│  Planner ─→ Actor (ReAct while loop) ─→ Evaluator
│     ↑                                    │   │
│     └──── replan / next task ────────────┘   │
│                                              │
└──────────────────────────────────────────────┘
    ↓ (목표 달성 or human 개입)
  Done
```

- **Planner**: 다음 1~2개 태스크만 생성 (진짜 rolling wave). DOM 안 봄.
- **Actor**: 배정받은 단일 태스크를 ReAct 루프로 실행. 매 스텝 DOM+Screenshot → LLM → 1 action → 실행 → 관찰.
- **Evaluator**: 구조화된 success criteria 체크 먼저, 애매하면 LLM 호출.

### 2. Actor = simple while loop (LangGraph subgraph 아님)

browser-use가 증명했듯이, step-by-step ReAct 루프는 단순 while loop이 가장 효과적. LangGraph는 외부 오케스트레이션(Planner → Actor → Evaluator 순환)에만 사용.

### 3. browser-use를 BrowserPort adapter로 감싸서 사용

browser-use (v0.11.9) public API를 활용:
- `BrowserSession.get_browser_state_summary()` → URL, title, DOM state, screenshot
- `SerializedDOMState.llm_representation()` → LLM용 DOM 텍스트
- event-driven 아키텍처 (`EventBus` 기반), 내부적으로 `cdp_use` 패키지 사용
- Paint order filtering, Shadow DOM, iframe 처리 내장

### 4. Plan Anchor 패턴

[WebAnchor (arXiv 2601.03164)](https://arxiv.org/abs/2601.03164)의 핵심 발견: **첫 번째 계획 스텝이 틀리면 전체 성공률이 23~31% 하락**한다. 논문은 이를 RL training(Anchor-GRPO)으로 해결하지만, surfy에서는 핵심 아이디어("첫 계획의 중요성")를 구조적으로 반영한다.

> **참고**: 논문의 self-validation rubric은 training-time reward signal이다. inference-time extra LLM call이 아님. surfy에서는 self-validation 없이 시작하고, 실패 패턴이 관측되면 그때 추가를 검토한다.

**a) Anchor = 불변 최종 목표**
```python
class Plan(BaseModel):
    anchor: str                     # 불변 최종 목표 (절대 변경 안 됨)
    tasks: list[Task]               # 현재 수립된 태스크들
    anchor_rationale: str           # 왜 이 분해가 anchor 달성에 최적인지
```

**b) Success Criteria**

각 태스크에 완료 조건을 부여. Planner는 DOM을 보지 않으므로 CSS selector 같은 구조적 필드는 사용하지 않는다:

```python
class SuccessCriteria(BaseModel):
    url_contains: str | None = None       # URL 패턴 (Planner가 예측 가능)
    text_visible: str | None = None       # 화면에 보여야 할 텍스트 (Planner가 예측 가능)
    description: str = ""                 # 자연어 설명 (항상 채움)
```

Evaluator는 구조 체크(URL, 텍스트) 먼저 → 판단 불가 시 LLM → 비용/지연 최소화.

**c) Replan은 실패한 구간만**

전체 계획을 버리지 않고, 실패한 태스크~anchor 구간만 재계획. 성공한 앞 단계는 보존.

## Hexagonal 디렉토리 구조

```
surfy/
├── domain/
│   ├── models/                  # 순수 도메인 모델 (프레임워크 의존 없음)
│   │   ├── plan.py              # Task, Plan, SuccessCriteria
│   │   ├── action.py            # BrowserAction (ActionType + target + value)
│   │   ├── screen.py            # PageState (URL, title, dom_text, screenshot)
│   │   └── result.py            # StepResult, EvalResult
│   ├── ports/                   # 인터페이스 (ABC)
│   │   ├── browser.py           # BrowserPort (get_state, execute_action, screenshot)
│   │   ├── llm.py               # LLMPort (plan, act, evaluate)
│   │   └── human.py             # HumanPort (ask, notify)
│   └── services/                # 도메인 서비스 (프롬프트 템플릿, 평가 로직)
│       ├── planner.py           # PlannerService — LLMPort 사용
│       ├── actor.py             # ActorService — LLMPort + BrowserPort, ReAct while loop
│       └── evaluator.py         # EvaluatorService — BrowserPort (구조 체크) + LLMPort (애매한 경우)
├── adapters/
│   ├── browser/
│   │   └── browser_use_adapter.py   # browser-use BrowserSession/DomService 래핑
│   ├── llm/
│   │   └── anthropic_adapter.py     # langchain-anthropic ChatAnthropic 래핑
│   └── human/
│       └── cli_adapter.py           # 터미널 입출력
├── graph.py                     # LangGraph 상태머신 (Planner → Actor → Evaluator 외부 루프)
├── state.py                     # LangGraph AgentState
└── main.py                      # Composition root (DI, 실행)
```

## 컴포넌트 상세

### Planner (domain/services/planner.py)

- **입력**: user_command + 지금까지의 진행 요약 (완료된 태스크 목록)
- **출력**: `Plan(anchor, tasks, anchor_rationale)`
- **특징**: DOM/Screenshot 안 봄 — 추상적 레벨에서만 작업
- **Anchor 패턴**:
  1. 첫 호출: anchor(불변 최종 목표) 설정 + 첫 1~2 태스크 생성
  2. 이후 호출: anchor 유지, 진행 상황 기반으로 다음 태스크만 생성 (rolling wave)
  3. Replan: 실패 구간만 재계획, anchor와 성공한 태스크는 보존
- **LLM 프롬프트**: structured output (JSON mode)으로 Plan 생성

### Actor (domain/services/actor.py)

- **입력**: 단일 Task (description + success criteria)
- **내부 루프**:
  ```
  while step < max_steps:
      page_state = browser_port.get_state()     # DOM text + screenshot
      action = llm_port.decide_action(task, page_state, history[-5:])
      result = browser_port.execute(action)
      history.append((action, result))
      if action.type == "DONE" or action.type == "STUCK":
          break
  ```
- **컨텍스트 관리**:
  - 현재 스텝: 전체 DOM text + screenshot
  - 최근 5 스텝: action + 결과 요약 (1줄씩)
  - 그 이전: 압축된 요약
- **max_actions_per_step**: 1 (안전) — 추후 form filling 등에서 batching 최적화 가능
- **LLM 출력 스키마**:
  ```python
  class ActorOutput(BaseModel):
      thinking: str           # 현재 상황 분석
      action_type: ActionType # CLICK, TYPE, SCROLL, GO_TO_URL, DONE, STUCK, ...
      target_id: int | None   # backend_node_id
      value: str | None       # TYPE시 입력값, GO_TO_URL시 URL
  ```

### Evaluator (domain/services/evaluator.py)

- **2단계 평가**:
  1. 구조 체크: URL 패턴, 텍스트 가시성 → BrowserPort로 확인
  2. LLM 체크: 구조 체크로 판단 불가시에만 호출 → 비용 절감
- **출력**: `EvalResult(success: bool, reason: str)`

### LangGraph Outer Loop (graph.py)

```python
def compile_graph():
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("actor", actor_node)          # 내부에서 while loop 실행
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("human_gateway", human_gateway_node)

    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", route_after_planner)  # → actor | human | END
    graph.add_edge("actor", "evaluator")
    graph.add_conditional_edges("evaluator", route_after_evaluator)  # → planner (next/replan) | human | END
    graph.add_edge("human_gateway", "planner")  # human 개입 후 planner로 복귀
```

### BrowserPort / BrowserUseAdapter (adapters/browser/)

```python
class BrowserPort(ABC):
    async def get_page_state(self) -> PageState:
        """DOM text + screenshot + URL + title"""

    async def execute_action(self, action: BrowserAction) -> StepResult:
        """click, type, scroll, navigate 등 실행"""

    async def check_text_visible(self, text: str) -> bool:
        """Evaluator의 구조 체크용"""

    async def connect(self, cdp_url: str) -> None:
        """기존 Chrome에 CDP 연결"""

    async def close(self) -> None:
```

`BrowserUseAdapter`는 browser-use의 `BrowserSession`, `DomService`, `DOMTreeSerializer`를 래핑.

### LLMPort / AnthropicAdapter (adapters/llm/)

```python
class LLMPort(ABC):
    async def plan(self, command: str, progress: str) -> Plan: ...
    async def decide_action(self, task: Task, page_state: PageState, history: list) -> ActorOutput: ...
    async def evaluate(self, criteria: SuccessCriteria, page_state: PageState) -> EvalResult: ...
```

각 메서드가 다른 프롬프트/스키마를 사용. `AnthropicAdapter`는 `langchain-anthropic`의 `ChatAnthropic`을 감싸되, 각 호출에 맞는 structured output 스키마를 적용. (self-validation 제거로 `validate_plan` 삭제됨 — 실패 패턴 관측 시 재검토)

## 구현 순서

### Phase 0: 문서화 + 프로젝트 초기화
1. **이 플랜을 `docs/0-initial-plan.md`로 저장** (프로젝트 기록)
2. 기존 `surfy/` 디렉토리 코드 삭제, Hexagonal 디렉토리 구조 생성
3. `pyproject.toml` 의존성 업데이트 (browser-use 추가)
4. `README.md` 업데이트 (새 아키텍처 반영)

### Phase 1: 기반 (브라우저 연결 + 화면 캡처)
1. `domain/ports/browser.py` — BrowserPort ABC 정의
2. `adapters/browser/browser_use_adapter.py` — browser-use 래핑, CDP 연결, get_page_state, execute_action
3. `domain/models/` — PageState, BrowserAction, ActionType 등 모델 정의
4. **검증**: CDP로 Chrome 연결 → DOM text + screenshot 정상 출력 확인

### Phase 2: Actor (핵심 루프)
1. `domain/ports/llm.py` — LLMPort ABC 정의
2. `adapters/llm/anthropic_adapter.py` — decide_action 구현
3. `domain/services/actor.py` — ReAct while loop 구현
4. **검증**: 단순 태스크 ("google.com에서 'hello' 검색") 수동 실행

### Phase 3: Planner + Evaluator
1. `domain/services/planner.py` + `domain/models/plan.py` (Task, SuccessCriteria)
2. `domain/services/evaluator.py` — 2단계 평가
3. `adapters/llm/anthropic_adapter.py` — plan, evaluate 메서드 추가
4. **검증**: 멀티스텝 태스크 ("네이버에서 날씨 검색 후 내일 기온 확인")

### Phase 4: LangGraph 오케스트레이션
1. `state.py` — AgentState 정의
2. `graph.py` — Planner → Actor → Evaluator 루프, retry/human 라우팅
3. `main.py` — DI composition root
4. **검증**: end-to-end 실행

### Phase 5: Human Gateway + 폴리싱
1. `adapters/human/cli_adapter.py` — 터미널 입출력
2. `domain/ports/human.py` — HumanPort ABC
3. human_gateway → planner 복귀 흐름

## 의존성 변경 (pyproject.toml)

```toml
dependencies = [
    "langgraph>=1.0.8",
    "langchain-core>=0.3",
    "langchain-anthropic>=0.3",
    "browser-use>=0.11",          # DOM 처리 + 브라우저 제어 (v0.11.9 기준 검증)
    "pydantic>=2.7",
]
# beautifulsoup4, Pillow 제거 (browser-use가 내부적으로 처리)
```

## 검증 방법

1. **Phase 1 검증**: `python -c "from surfy.adapters.browser... ; adapter.connect('http://localhost:9222'); print(adapter.get_page_state())"` — DOM text 출력 확인
2. **Phase 2 검증**: Actor 단독 실행으로 Google 검색 성공 여부
3. **Phase 3 검증**: Planner가 태스크 분해 → Actor 실행 → Evaluator 판정 흐름
4. **Phase 4 검증**: `python main.py "네이버에서 오늘 날씨 검색"` end-to-end
5. **Phase 5 검증**: retry 소진 후 human gateway → 사용자 입력 → 재개
