# Surfy

Hierarchical browser automation agent with Plan Anchor. Uses Hexagonal Architecture + LangGraph.

- Python 3.11+, managed by uv
- Key deps: langgraph, langchain-anthropic, browser-use, pydantic

## Commands

```bash
make check          # lint + typecheck + test (run before committing)
make lint           # uv run ruff check surfy/ tests/
make typecheck      # uv run pyright surfy/
make test           # uv run pytest tests/ -v --ignore=tests/test_phase1_integration.py -m "not real"
make fix            # auto-fix lint + format

# Single test
uv run pytest tests/test_evaluator.py -v
uv run pytest tests/test_evaluator.py -v -k "test_url_mismatch"
```

## Architecture — Hexagonal (Ports & Adapters)

```
surfy/
├── domain/
│   ├── models/      # Pure Pydantic models. No framework deps.
│   ├── ports/       # ABC interfaces. The contract with the outside world.
│   └── services/    # Business logic. Depends ONLY on ports, never on adapters.
├── adapters/
│   ├── browser/     # BrowserPort implementation (browser-use)
│   ├── llm/         # LLMPort implementation (langchain-anthropic)
│   └── research/    # ResearchPort implementation
├── graph.py         # LangGraph state machine (Planner → Actor → Evaluator loop)
├── state.py         # AgentState TypedDict for LangGraph
├── config.py        # Pydantic Settings
└── prompts/         # .prompty template files
```

### Dependency Rules (CRITICAL)

These are absolute rules. Violations break the architecture.

1. **domain/ must NOT import from adapters/**. Ever. Domain is pure.
2. **domain/services/ must depend on ports (ABC) only**. Constructor params must be port types.
3. **adapters/ may import from domain/ports and domain/models only**. Not from other adapters.
4. **graph.py imports services, not adapters**. Wiring happens in main.py.

```python
# ✅ CORRECT — service depends on port
class ActorService:
    def __init__(self, browser: BrowserPort, llm: LLMPort): ...

# ❌ WRONG — service depends on concrete adapter
class ScoutService:
    def __init__(self, agent: BrowserUseAgentAdapter): ...
```

### Adding New External Dependencies

When you need a new external system (API, database, etc.):

1. Define a port in `domain/ports/` (ABC with abstract methods)
2. Create adapter in `adapters/` implementing that port
3. Use the port type in services — never the adapter directly
4. Wire adapter → port in `main.py`

## Configuration & Dependency Injection

- **Config**: Use `surfy.config.Settings` (pydantic-settings) for all runtime values. Never hardcode API keys, URLs, timeouts, or model names in code.
- **Container**: Use `surfy.container.Container` (dependency-injector) for all object creation. Wire adapters → ports here, not in individual files.
- **main.py** is the composition root — it initializes the container and calls `container.init_resources()`.

```python
# ✅ CORRECT — read values from config, wire through container
class Container(containers.DeclarativeContainer):
    config = providers.Singleton(Settings)
    llm = providers.Singleton(AnthropicAdapter, model_name=config.provided.llm.model_name)
    actor_service = providers.Factory(ActorService, browser=browser, llm=llm)

# ❌ WRONG — hardcoded values, manual instantiation outside container
adapter = AnthropicAdapter(model_name="claude-sonnet-4-5-20250929")
service = ActorService(browser=adapter, llm=adapter)
```

## Code Style

### Formatting (enforced by ruff)
- Line length: 120 chars
- Target: Python 3.11
- Ruff rules: E (errors), F (pyflakes), I (isort)
- Run `make fix` to auto-format before committing

### Imports
- Absolute imports only: `from surfy.domain.models import Task`
- Order (enforced by isort): stdlib → third-party → local
- Use `__init__.py` re-exports: `from surfy.domain.models import Task` not `from surfy.domain.models.task import Task`
- When adding new public classes, update the relevant `__init__.py` and `__all__`

### Types
- All domain models use Pydantic `BaseModel`
- Enums use `(str, Enum)` pattern: `class ActionType(str, Enum)`
- Union types use `X | None` syntax (not `Optional[X]`)
- Type checker: pyright in basic mode

### Naming
- Classes: PascalCase (`PlannerService`, `BrowserPort`)
- Ports: `*Port` suffix (`BrowserPort`, `LLMPort`, `ResearchPort`)
- Adapters: `*Adapter` suffix (`AnthropicAdapter`, `BrowserUseAdapter`)
- Services: `*Service` suffix (`ActorService`, `EvaluatorService`)
- Private methods: `_prefix` (`self._llm`, `self._format_history()`)
- Files: snake_case matching the main class (`planner.py` → `PlannerService`)

### Docstrings
- Korean docstrings are used. Follow existing style.
- Module-level docstrings explain purpose and design decisions.
- Class and public method docstrings explain what, not how.

### Error Handling
- Let exceptions propagate unless you have a specific recovery strategy
- Use `logging.warning()` for recoverable failures, not silent catches
- Never catch bare `Exception` unless re-raising or in a top-level handler

## Testing

- Framework: pytest + pytest-asyncio
- Test files mirror source: `surfy/domain/services/planner.py` → `tests/test_planner.py`
- Mock ports with classes that implement the ABC. Do NOT use `unittest.mock` or `MagicMock` for ports.
- Marker `@pytest.mark.asyncio` for all async tests
- Marker `@pytest.mark.real` for tests requiring Chrome/API keys (excluded by default)

```python
# ✅ CORRECT — mock by implementing the port ABC
class MockBrowser(BrowserPort):
    async def get_page_state(self) -> PageState:
        return PageState(url="https://example.com", title="Test", dom_text="test")
    async def execute_action(self, action: BrowserAction) -> StepResult:
        return StepResult(success=True, message="OK")
    async def check_text_visible(self, text: str) -> bool:
        return True
    async def close(self) -> None:
        pass
```

## Prompts

LLM prompt templates live in `surfy/prompts/*.prompty` (YAML front-matter + Jinja2 body).

- **Do NOT hardcode prompts in Python code.** Create or edit a `.prompty` file instead.
- Existing templates: `actor.prompty`, `evaluator.prompty`, `planner.prompty`, `scout.prompty`
- Load with `_load_prompty("actor")` pattern (see `AnthropicAdapter` for reference).

## Agent Flow (LangGraph)

```
Research → Scout → Planner → [PlanApproval] → Actor → Evaluator
                     ↑                                    │
                     └──── replan / next task ─────────────┘
```

- **Planner**: Generates 1-2 tasks at a time (rolling wave). Does NOT see DOM.
- **Actor**: Executes a single task via ReAct loop (observe → think → act). Sees DOM + screenshot.
- **Evaluator**: 2-stage check. Structural (URL, text) first → LLM fallback if ambiguous.
- **graph.py is orchestration only.** No `print()`, `input()`, or direct UI logic. Human interaction must go through a port.

## Browser Principle (CRITICAL)

**Surfy는 반드시 사용자가 이미 띄운 Chrome 브라우저에서 작업한다.** 이것이 핵심 원칙이다.

- Surfy는 별도 Chrome을 띄우지 않는다. 사용자의 Chrome에 CDP(Chrome DevTools Protocol)로 연결하여 작업한다.
- 이유: 사용자가 로그인한 세션, 쿠키, 확장 프로그램 등을 그대로 활용해야 실제 사용자 경험과 동일한 자동화가 가능하다.

### 연결 방법별 한계 (Known Issues)

현재 사용자의 메인 Chrome 프로필에서 완벽하게 동작하는 연결 방법은 없으며, 이는 미해결 아키텍처 이슈입니다.

| 방법 | 설정 | 한계 |
|------|------|------|
| `use_system_chrome=true` | browser-use가 시스템 Chrome 프로필로 직접 연결 | Chrome이 이미 실행 중이면 **프로필 잠금(lock) 충돌** 발생 → `session.start()` 실패 또는 불안정 |
| CDP 모드 (기본 프로필) | `--remote-debugging-port=9222`로 Chrome 실행 | **Chrome 136+ 보안 정책 변경**으로 인해 기본 프로필 경로에서의 CDP 연결이 차단됨 |
| CDP 모드 (별도 프로필) | `--remote-debugging-port=9222 --user-data-dir=/tmp/chrome-cdp-profile` | 정상 동작하지만 **깨끗한 프로필**로 시작됨 → 사용자 쿠키/세션이 없어 핵심 원칙 위반 |

### 현재 권장 설정 (임시 워크어라운드)

사용자가 이미 Chrome을 띄운 상태에서는 CDP 연결이 불가능하므로, 기존에 실행 중인 Chrome을 모두 닫고 아래와 같이 CDP 모드로 재시작해야 합니다.

```bash
# 1. 모든 Chrome 프로세스 종료 후 CDP 모드로 실행
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# 2. .env 설정
BROWSER_USE_SYSTEM_CHROME=false
BROWSER_CDP_URL=http://localhost:9222

# 3. 서버 시작
uv run python main.py --serve --port 8765
```

### 왜 `use_system_chrome=true`가 안 되는가

Chrome은 프로필 디렉토리를 잠금(lock)한다. 사용자가 Default 프로필로 Chrome을 이미 띄운 상태에서 browser-use가 같은 프로필로 연결을 시도하면:
1. `BrowserSession(user_data_dir=..., profile_directory="Default")` → 프로필 잠금 충돌
2. `session.start()` 실패 또는 불안정한 연결
3. 서버의 `_browser_watchdog()`가 `_is_browser_alive()=False` 감지 → 전체 graph task 취소
4. WebSocket 끊김 → Extension "Disconnected"

### 미해결 과제

사용자 경험을 해치지 않으면서 메인 프로필에 안정적으로 연결하기 위해 아래 방향들을 검토 중입니다:
1. Extension의 `chrome.debugger` API를 사용하여 Extension 내부에서 직접 브라우저를 제어
2. browser-use 라이브러리의 CDP 대안 경로 탐색
3. Chrome 시작 시 별도 프로필로 CDP를 열되, 사용자 프로필 데이터를 복사 또는 심볼릭 링크로 연결


## Phase 5: Browser Extension (WebSocket + Chrome Extension)

### Architecture

FastAPI 서버(`surfy/server.py`)가 LangGraph와 Chrome Extension 사이의 브릿지 역할을 수행합니다.
- LangGraph의 `interrupt()` 패턴을 사용하여 HITL(Human-In-The-Loop)을 구현하며, 기존의 print/input 방식을 대체합니다.
- `MemorySaver`를 사용하여 체크포인트 영속성을 유지합니다.
- 단일 세션, localhost 전용으로 동작합니다.

### Running Server Mode

```bash
# Chrome CDP 먼저 실행 (필수 — Browser Principle 참조)
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# 서버 시작
uv run python main.py --serve --port 8765
```

### Extension Build & Load

```bash
cd extension && npm install && npm run build
```
Chrome에서 로드: `chrome://extensions` → 개발자 모드 → 압축해제된 확장 프로그램을 로드합니다 → `extension/dist` 디렉토리 선택

### WebSocket Protocol

| Type | Direction | Description |
|------|-----------|-------------|
| run | C→S | 에이전트 실행 시작 |
| resume | C→S | interrupt에 대한 사용자 응답 |
| chat | C→S | 실행 중 메시지 큐잉 |
| cancel | C→S | 실행 중인 태스크 취소 |
| node_start/node_end | S→C | 노드 생명주기 이벤트 |
| state_update | S→C | 상태 변경 알림 |
| interrupt | S→C | 사용자 개입 필요 알림 |
| dom_highlight | S→C | DOM 하이라이트 토글 |
| connected | S→C | 연결 수립 및 초기 상태 전송 |
| heartbeat | Both | 연결 유지용 하트비트 |

### New Files

- `surfy/server.py` — FastAPI WebSocket 서버
- `surfy/state.py` — `user_feedback` 필드가 포함된 AgentState
- `surfy/domain/models/messages.py` — WebSocket 메시지 프로토콜 모델
- `extension/` — Chrome Extension MV3 (React + Tailwind + Vite)

## Observability (LangSmith / Langfuse + LangGraph Studio)

두 가지 트레이싱 옵션이 있다. 둘 다 동시에 켤 수도 있지만, 일반적으로 하나만 선택.

| | LangSmith (SaaS) | Langfuse (Self-hosted) |
|---|---|---|
| 비용 | Free 5,000 traces/month, 팀 초대 시 $39/user/month | 무료 (Docker로 직접 운영) |
| 설치 | 환경변수 3개 | Docker Compose + 환경변수 3개 |
| 팀 공유 | 유료 플랜 필요 | 무제한 사용자, 무료 |
| 적합한 경우 | 개인 개발, 빠른 시작 | 팀 QA/디버깅, 비용 제한 환경 |

### LangSmith (SaaS 트레이싱)

Zero-code 설정 — 환경변수 3개만 추가하면 LangGraph 노드 + LLM 호출 자동 추적.

```bash
# .env에 추가 (또는 export)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_xxxx    # https://smith.langchain.com 에서 발급
LANGSMITH_PROJECT=surfy
```

- Free tier: 5,000 traces/month, 14일 보존
- LangGraph 노드 실행, LLM prompt/response, 상태 전이 자동 캡처
- browser-use Agent 내부는 자동 트레이싱 안 됨 → `@traceable` 래퍼 필요 시 추가
- 대시보드: https://smith.langchain.com

### Langfuse (Self-hosted 트레이싱)

팀원들이 무료로 트레이스를 확인할 수 있는 오픈소스 대안. MIT 라이선스.

#### 1. Langfuse 서버 실행

```bash
# 프로젝트 루트에서
docker compose -f docker-compose.langfuse.yml up -d
```

- PostgreSQL + Langfuse 웹 서버가 `http://localhost:3000`에 뜸
- 최초 접속 시 회원가입 → 프로젝트 생성 → API 키 발급

#### 2. 환경변수 설정

```bash
# .env에 추가
LANGFUSE_PUBLIC_KEY=pk-lf-xxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxx
LANGFUSE_BASE_URL=http://localhost:3000
```

#### 3. 동작 방식

- `surfy/observability.py`의 `create_langfuse_handler()`가 환경변수를 감지하여 `langfuse.langchain.CallbackHandler` 생성
- `server.py`에서 `compiled_graph.with_config({"callbacks": [handler]})`로 자동 연결
- 환경변수가 없으면 핸들러를 생성하지 않음 — 성능 영향 없음

#### 4. 대시보드

- `http://localhost:3000`에서 트레이스 확인
- 팀원 초대: Settings → Members → 이메일로 초대 (무제한, 무료)

### LangGraph Studio (시각화 & 데모)

그래프 노드를 실시간 시각화하고 시간여행 디버깅 가능. 데모에 최적.

```bash
# 설치
pip install "langgraph-cli[inmem]"

# 실행 (프로젝트 루트에서)
langgraph dev
```

- 설정 파일: `langgraph.json` (프로젝트 루트)
- 엔트리포인트: `surfy/graph_studio.py:graph`
- Studio에서 그래프 구조 + 상태 + 노드별 입출력 확인 가능

### 디버깅 워크플로우

```bash
# 1. LangSmith 또는 Langfuse로 최근 실행 확인
#    → LangSmith: https://smith.langchain.com
#    → Langfuse: http://localhost:3000

# 2. LangGraph Studio로 인터랙티브 디버깅
langgraph dev
#    → 브라우저에서 http://127.0.0.1:8123 접속

# 3. E2E 테스트 (실제 브라우저 필요)
uv run python main.py "네이버에서 오늘 서울 날씨 검색해줘"
```

### 주의사항

- API 키는 `.env`에만 넣고, **절대 코드에 하드코딩하지 말 것**
- `LANGSMITH_TRACING=true`가 없으면 LangSmith 트레이싱 비활성
- `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`가 없으면 Langfuse 트레이싱 비활성
- Studio는 로컬 개발용 — 프로덕션에서는 LangSmith 또는 Langfuse 대시보드 사용

## Behavioral Rules

- State assumptions explicitly before implementing. If unclear, ask.
- Minimum code that solves the problem. No speculative features.
- Touch only what you must. Don't improve adjacent code unless asked.
- Every changed line must trace to the request. Remove only YOUR orphaned imports.
- Run `make check` after changes. Fix any errors you introduce.
