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

## Observability (LangSmith + LangGraph Studio)

### LangSmith (트레이싱)

Zero-code 설정 — 환경변수 3개만 추가하면 LangGraph 노드 + LLM 호출 자동 추적.

```bash
# .env에 추가 (또는 export)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_xxxx    # https://smith.langchain.com 에서 발급
LANGSMITH_PROJECT=surfy
```

- Free tier: 5,000 traces/month
- LangGraph 노드 실행, LLM prompt/response, 상태 전이 자동 캡처
- browser-use Agent 내부는 자동 트레이싱 안 됨 → `@traceable` 래퍼 필요 시 추가
- 대시보드: https://smith.langchain.com

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
# 1. LangSmith로 최근 실행 확인
#    → https://smith.langchain.com 에서 프로젝트 선택 → Runs 탭

# 2. LangGraph Studio로 인터랙티브 디버깅
langgraph dev
#    → 브라우저에서 http://127.0.0.1:8123 접속

# 3. E2E 테스트 (실제 브라우저 필요)
uv run python main.py "네이버에서 오늘 서울 날씨 검색해줘"
```

### 주의사항

- LangSmith API 키는 `.env`에만 넣고, **절대 코드에 하드코딩하지 말 것**
- `LANGSMITH_TRACING=true`가 없으면 트레이싱 비활성 (성능 영향 없음)
- Studio는 로컬 개발용 — 프로덕션에서는 LangSmith 대시보드 사용

## Behavioral Rules

- State assumptions explicitly before implementing. If unclear, ask.
- Minimum code that solves the problem. No speculative features.
- Touch only what you must. Don't improve adjacent code unless asked.
- Every changed line must trace to the request. Remove only YOUR orphaned imports.
- Run `make check` after changes. Fix any errors you introduce.
