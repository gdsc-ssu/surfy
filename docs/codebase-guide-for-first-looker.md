# Surfy 코드베이스 가이드

## 1. Surfy란?

사용자의 자연어 명령을 받아 Chrome 브라우저를 자동 조작하는 AI 에이전트다.

예: 사용자가 `"네이버에서 오늘 서울 날씨 검색해줘"`라고 입력하면, Surfy가 네이버 접속 → 검색어 입력 → 검색 실행 → 결과 확인까지 자동으로 수행한다.

---

## 2. 에이전트 구성 요소

Surfy는 5개의 역할로 나뉘어 동작한다. 각 컴포넌트는 자기 역할만 수행하며, 다른 컴포넌트의 책임을 침범하지 않는다.

| 컴포넌트 | 역할 | 입력 | 출력 |
|----------|------|------|------|
| **Researcher** | 웹 검색으로 사전 정보 수집 | 사용자 명령 | `ResearchResult` |
| **Scout** | 브라우저로 목표 사이트를 미리 탐색 | 사용자 명령 + 리서치 결과 | `RouteMap` |
| **Planner** | 명령을 실행 가능한 태스크로 분해 | 명령 + RouteMap + ResearchResult | `Plan` |
| **Actor** | 브라우저에서 태스크를 실제 실행 | `Task` | `StepResult` |
| **Evaluator** | 태스크가 성공했는지 판정 | `Task` + `PageState` | `EvalResult` |

Planner는 브라우저 화면(DOM)을 보지 않고, Actor는 전체 계획을 세우지 않고, Evaluator는 행동하지 않고 판정만 한다.

---

## 3. 아키텍처: Hexagonal Architecture (Ports & Adapters)

### 3-1. 문제: 외부 시스템에 직접 의존하면?

```python
# 이런 코드의 문제점
def do_task(command):
    response = openai.chat.completions.create(model="gpt-4", ...)  # OpenAI에 직접 의존
    browser = sync_playwright().chromium.launch()                   # Playwright에 직접 의존
    page.click(response.action)
```

- LLM을 OpenAI에서 Anthropic으로 교체하려면 비즈니스 로직까지 수정해야 한다
- 테스트할 때 실제 Chrome과 실제 API를 호출해야 한다
- 변경의 영향 범위를 예측할 수 없다

### 3-2. 해결: 비즈니스 로직과 외부 시스템을 분리

```
+---------------------------------------------+
|            domain/ (비즈니스 로직)             |
|                                             |
|  models/   -> 데이터 구조 (Pydantic 모델)     |
|  ports/    -> 인터페이스 (ABC 추상 클래스)     |
|  services/ -> 핵심 로직 (Planner, Actor 등)   |
|                                             |
|      외부 라이브러리를 절대 import하지 않음     |
+---------------------------------------------+
|        adapters/ (외부 시스템 연결)            |
|                                             |
|  llm/      -> Claude, Gemini 연결           |
|  browser/  -> Chrome 브라우저 연결            |
|  research/ -> 웹 검색 엔진 연결              |
|                                             |
|      domain/ports의 ABC를 구현함             |
+---------------------------------------------+
```

**의존성 규칙**: `domain/`은 `adapters/`를 절대 import하지 않는다. 반대 방향만 허용된다.

### 3-3. Port와 Adapter

- **Port** = 추상 클래스(ABC). 서비스가 필요한 기능의 인터페이스를 정의한다.
- **Adapter** = Port를 구현하는 구체 클래스. 실제 외부 시스템과 통신한다.

```python
# Port — 브라우저가 제공해야 할 기능의 인터페이스
class BrowserPort(ABC):
    @abstractmethod
    async def get_page_state(self) -> PageState: ...

    @abstractmethod
    async def execute_action(self, action: BrowserAction) -> StepResult: ...

    @abstractmethod
    async def check_text_visible(self, text: str) -> bool: ...

# Adapter — browser-use 라이브러리로 BrowserPort를 구현
class BrowserUseAdapter(BrowserPort):
    async def get_page_state(self) -> PageState:
        # 실제 Chrome에서 URL, 제목, DOM 텍스트 추출
        ...

    async def execute_action(self, action: BrowserAction) -> StepResult:
        # 실제 Chrome에서 클릭, 타이핑, 스크롤 수행
        ...
```

이 구조의 장점:
- **교체 용이**: Chrome 대신 Firefox를 쓰려면 `FirefoxAdapter`만 만들면 된다. 서비스 코드는 그대로.
- **테스트 용이**: 실제 브라우저 없이 `MockBrowser(BrowserPort)`를 구현해서 테스트할 수 있다.
- **변경 격리**: 외부 라이브러리 API가 바뀌어도 Adapter만 수정하면 된다.

---

## 4. 핵심 데이터 모델

모든 데이터는 Pydantic `BaseModel`로 정의된다. 각 컴포넌트 사이를 오가는 입출력 타입들이다.

```python
# Task — 실행할 단일 작업 단위
class Task(BaseModel):
    description: str                    # "네이버 검색창에 '서울 날씨' 입력"
    success_criteria: SuccessCriteria   # 완료 판정 기준
    target_url: str | None = None       # Scout이 발견한 목표 URL

# Plan — 최종 목표(anchor) + 현재 태스크 목록
class Plan(BaseModel):
    anchor: str            # "네이버에서 서울 날씨 검색" — 절대 변경되지 않는 최종 목표
    tasks: list[Task]      # 현재 수립된 태스크들 (1~2개씩 rolling wave로 생성)
    anchor_rationale: str  # 이 분해가 anchor 달성에 최적인 이유

# PageState — 현재 브라우저 페이지 상태
class PageState(BaseModel):
    url: str               # "https://www.naver.com"
    title: str             # "네이버"
    dom_text: str          # 페이지의 텍스트 내용
    screenshot: str | None # base64 인코딩된 스크린샷

# ActionType — Actor가 수행할 수 있는 브라우저 행동
class ActionType(str, Enum):
    CLICK = "CLICK"
    TYPE = "TYPE"
    SCROLL_DOWN = "SCROLL_DOWN"
    SCROLL_UP = "SCROLL_UP"
    GO_TO_URL = "GO_TO_URL"
    SEND_KEYS = "SEND_KEYS"
    GO_BACK = "GO_BACK"
    DONE = "DONE"     # 태스크 완료 선언
    STUCK = "STUCK"   # 진행 불가 선언

# StepResult — Actor의 단일 액션 실행 결과
class StepResult(BaseModel):
    success: bool
    message: str
    page_state: PageState | None = None

# EvalResult — Evaluator의 태스크 완료 판정
class EvalResult(BaseModel):
    success: bool
    reason: str   # 판정 근거
```

이 모델들이 컴포넌트 간 데이터 전달의 계약(contract) 역할을 한다.

---

## 5. 서비스 상세

### 5-1. PlannerService

사용자 명령을 태스크 단위로 분해한다. LLM에게 계획 수립을 요청하되, DOM은 보지 않는다.

```python
class PlannerService:
    def __init__(self, llm: LLMPort):   # Port 타입에만 의존
        self._llm = llm

    async def create_plan(self, command, route_map, research_result) -> Plan:
        # 첫 호출: anchor 설정 + 첫 1~2개 태스크 생성

    async def next_tasks(self, plan, completed_tasks) -> Plan:
        # 이후 호출: anchor 유지, 진행 상황 기반 다음 태스크 생성

    async def replan(self, plan, failed_task, reason) -> Plan:
        # 실패 시: anchor 유지, 실패 구간만 재계획
```

**Plan Anchor 패턴**: `anchor`(최종 목표)는 어떤 상황에서도 변경되지 않는다. 태스크가 실패하면 해당 부분만 재계획한다. WebAnchor 논문에 따르면, 첫 번째 계획 스텝이 틀리면 전체 성공률이 23~31% 하락한다.

**Rolling Wave**: 전체 태스크를 한 번에 생성하지 않고 1~2개씩 점진적으로 생성한다. 이전 태스크의 실행 결과를 반영하여 다음 태스크를 더 정확하게 만들 수 있다.

### 5-2. ActorService

단일 태스크를 ReAct(Reason + Act) 루프로 실행한다.

```python
class ActorService:
    def __init__(self, browser: BrowserPort, llm: LLMPort):
        self._browser = browser
        self._llm = llm

    async def execute_task(self, task: Task, max_steps: int = 15) -> StepResult:
        for step in range(max_steps):
            page_state = await self._browser.get_page_state()       # 1. 관찰
            output = await self._llm.decide_action(task, page_state, history)  # 2. 판단

            if output.action_type == ActionType.DONE:               # 3a. 완료
                return StepResult(success=True, ...)
            if output.action_type == ActionType.STUCK:              # 3b. 실패
                return StepResult(success=False, ...)

            result = await self._browser.execute_action(output.to_browser_action())  # 3c. 실행
```

매 스텝마다 `관찰 → 판단 → 실행`을 반복한다. 루프 감지 로직이 있어서, 같은 페이지 상태가 5회 연속 반복되면 STUCK으로 종료한다.

### 5-3. EvaluatorService

태스크 성공 여부를 2단계로 판정한다.

```python
class EvaluatorService:
    async def evaluate(self, task: Task, page_state: PageState) -> EvalResult:
        criteria = task.success_criteria

        # 1단계: 구조 체크 (비용 없음)
        if criteria.url_contains and criteria.url_contains not in page_state.url:
            return EvalResult(success=False, reason="URL 불일치")

        if criteria.text_visible:
            visible = await self._browser.check_text_visible(criteria.text_visible)
            if not visible:
                return EvalResult(success=False, reason="텍스트 미표시")

        # 2단계: LLM 판정 (구조 체크로 판단 불가한 경우에만)
        if criteria.description:
            return await self._llm.evaluate(criteria, page_state)

        return EvalResult(success=True, reason="구조 체크 통과")
```

LLM 호출은 비용과 시간이 들기 때문에, URL 패턴이나 텍스트 존재 여부 같은 구조적 체크를 먼저 수행한다. 그것으로 판단이 안 될 때만 LLM을 호출한다.

### 5-4. ScoutService / ResearcherService

Actor가 본격적으로 실행하기 전에 사전 정보를 수집하는 단계다.

```python
# Scout: 브라우저로 목표 사이트를 미리 탐색하여 경로 정보 수집
class ScoutService:
    def __init__(self, scout: ScoutPort):
        self._scout = scout

    async def scout(self, command, max_steps=20, ...) -> RouteMap:
        return await self._scout.explore(task=f"정찰: {command}", max_steps=max_steps)

# Researcher: 웹 검색 API로 관련 정보 수집
class ResearcherService:
    def __init__(self, research_port: ResearchPort):
        self._research_port = research_port

    async def research(self, command) -> ResearchResult:
        return await self._research_port.research(command)
```

Scout의 결과(`RouteMap`)와 Researcher의 결과(`ResearchResult`)는 Planner에 전달되어 더 정확한 계획 수립에 활용된다.

---

## 6. LangGraph 상태 머신

### 6-1. AgentState

LangGraph가 관리하는 전체 상태다. 각 노드는 이 상태의 일부를 읽고 업데이트한다.

```python
class AgentState(TypedDict):
    command: str                        # 사용자 명령
    plan: Plan | None                   # 현재 계획
    route_map: RouteMap | None          # Scout 정찰 결과
    current_task_idx: int               # 현재 실행 중인 태스크 인덱스
    eval_result: EvalResult | None      # 마지막 평가 결과
    retry_count: int                    # 현재 태스크 재시도 횟수
    max_retries: int                    # 최대 재시도 허용 횟수
    history: Annotated[list[HistoryEntry], operator.add]   # 행동 기록 (누적)
    completed_tasks: Annotated[list[Task], operator.add]   # 완료된 태스크 (누적)
    last_page_state: PageState | None   # 마지막 페이지 상태
    plan_approved: bool                 # 사용자 계획 승인 여부
    user_feedback: str | None           # 사용자 피드백
    done: bool                          # 종료 여부
    error: str | None                   # 에러 메시지
```

`Annotated[list, operator.add]`는 LangGraph의 리듀서(reducer)로, 해당 필드가 덮어쓰기가 아닌 누적(append) 방식으로 업데이트된다.

### 6-2. 그래프 흐름

```
[시작]
   |
   v
Research --> Scout --> Planner --> Plan Approval --> Actor --> Evaluator
                         ^            |                          |
                         |            +-- 거부 --> END           +-- 성공, 다음 태스크 있음 --> Actor
                         |            +-- 수정 --> Planner       +-- 성공, 전부 완료 --> Completion Check
                         |                                       +-- 실패, 재시도 가능 --> Planner
                         +---------------------------------------+-- 실패, 한계 초과 --> Human Gateway
                                                                                    |
                                                                              +-- 재시도 --> Planner
                                                                              +-- 포기 --> END
```

LangGraph 핵심 개념:
- **Node**: 각 처리 단계를 담당하는 async 함수. `AgentState`를 받아 업데이트할 필드를 dict로 반환한다.
- **Edge**: 노드 간 고정 연결. 예: `actor` → `evaluator`
- **Conditional Edge**: 상태에 따라 다음 노드를 결정하는 라우팅 함수.
- **interrupt()**: 그래프 실행을 일시 중단하고 사용자 입력을 기다린다 (Human-in-the-Loop).

### 6-3. 조건부 라우팅 예시

```python
def route_after_evaluator(state):
    if state["done"]:
        return "END"

    eval_result = state["eval_result"]

    if eval_result.success:
        task = _current_task(state)
        if task is not None:
            return "actor"           # 다음 태스크 실행
        return "completion_check"    # 모든 태스크 완료

    if state["retry_count"] <= state["max_retries"]:
        return "planner"             # 재계획 후 재시도
    return "human_gateway"           # 사용자에게 판단 위임
```

평가 결과와 현재 상태를 기반으로 다음에 실행할 노드를 결정한다.

---

## 7. 실행 시나리오

사용자가 `"네이버에서 오늘 서울 날씨 검색해줘"`를 입력했을 때의 실행 흐름:

```
1. [Research]      웹 검색으로 관련 정보 수집
                   -> ResearchResult(summary="naver.com에서 검색 가능", sources=["naver.com"])

2. [Scout]         Chrome으로 naver.com을 미리 탐색
                   -> RouteMap(final_url="https://www.naver.com", scout_summary="검색창 확인됨")

3. [Planner]       리서치 + 정찰 결과를 기반으로 계획 수립
                   -> Plan(anchor="네이버에서 오늘 서울 날씨 검색",
                           tasks=[Task(description="검색창에 '서울 날씨' 입력 후 검색")])

4. [Plan Approval] interrupt()로 실행 중단, 사용자에게 계획 승인 요청
                   사용자 승인 -> 재개

5. [Actor]         ReAct 루프 실행:
                   Step 1: 페이지 관찰 -> LLM 판단: TYPE(target=17, value="서울 날씨") -> 실행
                   Step 2: 페이지 관찰 -> LLM 판단: SEND_KEYS(value="Enter") -> 실행
                   Step 3: 페이지 관찰 -> LLM 판단: DONE -> 종료
                   -> StepResult(success=True, message="검색 완료")

6. [Evaluator]     SuccessCriteria 기반 판정
                   url_contains 체크 통과 -> EvalResult(success=True)

7. [Completion]    interrupt()로 사용자에게 추가 작업 여부 확인
                   사용자: 종료 -> END
```

---

## 8. 의존성 주입

`main.py`가 Composition Root 역할을 한다. 여기서 어댑터를 생성하고, 서비스에 주입하고, 그래프를 조립한다.

```python
# 1. 어댑터 생성 — 실제 외부 시스템 연결
browser = await BrowserUseAdapter.create(...)
llm = LangChainLLMAdapter(model=chat_model, ...)
researcher = ResearcherService(research_port=DdgsSearchAdapter())

# 2. 서비스 생성 — 어댑터를 Port 타입으로 주입
planner = PlannerService(llm=llm)                # llm: LLMPort
actor = ActorService(browser=browser, llm=llm)   # browser: BrowserPort, llm: LLMPort
evaluator = EvaluatorService(browser=browser, llm=llm)
scout = ScoutService(scout=agent_adapter)         # scout: ScoutPort

# 3. 그래프 조립
graph = compile_graph(scout, planner, actor, evaluator, researcher)
```

서비스는 생성자에서 Port 타입(ABC)을 받는다. 어떤 구체적인 Adapter가 들어오는지는 서비스가 모른다. `main.py`에서 `BrowserUseAdapter`를 넣든, 테스트에서 `MockBrowser`를 넣든 서비스 코드는 동일하다. 이것이 의존성 주입(Dependency Injection)이다.

---

## 9. Extension + Server

CLI 모드 외에, Chrome Extension + WebSocket 서버로 동작한다.

```
Chrome Extension (Side Panel UI)
      | WebSocket (ws://localhost:8765)
      v
FastAPI Server (surfy/server.py)
      |
      v
LangGraph 상태 머신
      |
      v
Chrome (CDP, port 9222)
```

- Extension에서 사용자가 명령 입력 → WebSocket으로 서버에 전달
- 서버가 LangGraph 실행 → 노드 진행 상황을 WebSocket으로 Extension에 실시간 전달
- `interrupt()` 발생 시 Extension에 승인 UI 표시 → 사용자 응답을 서버로 전달하여 재개

---

## 10. 요약

### 핵심 개념 5가지

| 개념 | 설명 |
|------|------|
| **Hexagonal Architecture** | 비즈니스 로직(domain)과 외부 시스템(adapters)을 Port(ABC)로 분리 |
| **Plan Anchor** | 최종 목표(anchor)를 불변으로 유지하고, 실패 시 해당 구간만 재계획 |
| **ReAct Loop** | 관찰 → 판단 → 실행을 반복하여 태스크 수행 |
| **2단계 평가** | 비용 없는 구조 체크 우선, 판단 불가 시에만 LLM 호출 |
| **LangGraph 상태 머신** | 노드별 역할 분담 + 조건부 라우팅으로 실행 흐름 제어 |

### 디렉토리 구조

```
surfy/
├── domain/
│   ├── models/      # 데이터 모델 (Task, Plan, PageState 등)
│   ├── ports/       # 인터페이스 정의 (BrowserPort, LLMPort 등)
│   └── services/    # 비즈니스 로직 (PlannerService, ActorService 등)
├── adapters/
│   ├── browser/     # BrowserPort 구현 (browser-use)
│   ├── llm/         # LLMPort 구현 (langchain)
│   └── research/    # ResearchPort 구현 (DuckDuckGo)
├── graph.py         # LangGraph 상태 머신 정의
├── state.py         # AgentState TypedDict
├── server.py        # FastAPI WebSocket 서버
├── config.py        # Pydantic Settings 설정
└── prompts/         # LLM 프롬프트 템플릿 (.prompty)
```
