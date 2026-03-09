# Phase 4: LangGraph 통합 계획

## 목표
LangGraph를 도입해 Outer Loop(Planner → Actor → Evaluator)를 상태 머신으로 오케스트레이션한다. 이를 통해 기존 Hexagonal Architecture(도메인 서비스 + 어댑터)를 실제 E2E 실행 파이프라인으로 연결한다.

## 1) `AgentState` 구현 (`surfy/state.py`)

LangGraph 상태는 엄격한 타입이 필요하며, 리스트 필드는 누적(append) 동작을 위해 reducer를 명시해야 한다.

- `surfy/state.py` 생성
- `AgentState`를 `TypedDict`로 정의
- 필요한 도메인 모델 import 정리
- 필수 필드:
  - `command: str`
  - `plan: Plan | None`
  - `current_task_idx: int`
  - `eval_result: EvalResult | None`
  - `retry_count: int`
  - `max_retries: int`
  - `history: Annotated[list[HistoryEntry], operator.add]`
  - `completed_tasks: Annotated[list[Task], operator.add]`
  - `last_page_state: PageState | None`
  - `done: bool`
  - `error: str | None`

### 상태 마이그레이션 방침 (P0 반영)

현재 런타임은 루트 `main.py`의 `initial_state`에서 아래 키를 사용 중이다:
- `user_command`, `macro_plan`, `current_micro_plan`, `current_screen`
- `last_execution_result`, `last_review_result`
- `execution_history`, `review_history`
- `micro_retry_count`, `macro_retry_count`, `max_micro_retries`, `max_macro_retries`
- `needs_human_intervention`, `is_complete`

**Phase 4에서는 위 키를 유지하지 않고, `AgentState`로 전면 교체한다.**

- 교체 대상 파일: `main.py` (루트 파일)
- 전환 규칙:
  - `user_command` → `command`
  - `execution_history`/`review_history` → `history`/`completed_tasks` 중심으로 재구성
  - `*_retry_*` 이원화 키 → `retry_count`, `max_retries` 단일 정책
  - `is_complete`/`needs_human_intervention` → `done` + `human_gateway` 라우팅으로 대체
- 호환성 전략: Phase 4 범위에서는 레거시 키를 병행 유지하지 않음 (혼합 상태 금지)

## 2) 그래프 오케스트레이션 구현 (`surfy/graph.py`)

Hexagonal Architecture를 유지하기 위해 그래프는 서비스 의존성을 주입받는 팩토리 함수로 설계한다.

- `surfy/graph.py` 생성
- `compile_graph(planner, actor, evaluator, checkpointer=None) -> CompiledGraph` 구현
- 노드 정의:
  - `planner_node(state)`
    - `plan is None`이면 `create_plan(command)`
    - `eval_result.success is False`이면 `replan(...)`
    - 성공 후 현재 wave 종료 시 `next_tasks(...)`
    - 새 plan/tasks 생성 시 `retry_count` 리셋
  - `actor_node(state)`
    - 현재 task 실행: `actor.execute_task(...)`
    - `history`, `last_page_state` 업데이트
  - `evaluator_node(state)`
    - `evaluator.evaluate(...)` 호출
    - `eval_result` 업데이트
  - `human_gateway_node(state)`
    - Phase 4 임시 구현: `input()` 기반 개입
    - `exit` 입력 시 `done=True`
- 라우팅 정의:
  - `route_after_planner(state) -> Literal["actor", "END"]`
  - `route_after_evaluator(state) -> Literal["planner", "actor", "human_gateway", "END"]`
    - 성공 + 남은 task 있음 → `actor`
    - 성공 + 남은 task 없음 → `planner`(다음 wave)
    - 실패 + 재시도 가능 → `planner`
    - 실패 + 재시도 초과 → `human_gateway`

## 3) Composition Root 구현 (`main.py`, `surfy/__main__.py`)

- `main.py`(루트) 수정
  - `run(command: str)` / `main(command: str)` 진입점 구성
  - `BrowserUseAdapter`, `AnthropicAdapter` 생성
  - `PlannerService`, `ActorService`, `EvaluatorService` 조립
  - `MemorySaver` 체크포인터 생성
  - `compile_graph(...)` 호출
  - 초기 상태를 레거시 dict가 아닌 `AgentState`로 생성하여 그래프 실행
  - 브라우저 생명주기 `finally`에서 정리
- `surfy/__main__.py` 생성
  - `python -m surfy "..."` 실행 가능하도록 CLI 엔트리 추가

## 4) 최종 검증

### 시나리오 A — 기본 실행 검증

1. Chrome CDP 실행
   - macOS: `/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222`
2. 에이전트 실행
   - `uv run python -m surfy "네이버에서 오늘 날씨 검색"`
3. 기대 결과
   - 로그에 `planner -> actor -> evaluator` 순서가 최소 1회 이상 나타남
   - 프로세스가 예외 없이 종료되고 브라우저 세션이 정리됨

### 시나리오 B — MemorySaver(thread_id) 상태 유지 검증

1. 동일 `thread_id`를 코드에서 고정(예: `surfy-phase4-test`)하고 1차 실행
2. 동일 명령 + 동일 `thread_id`로 2차 실행
3. 기대 결과
   - 2차 실행 시 체크포인터가 기존 스레드 상태를 조회하는 로그/동작이 확인됨
   - 상태 키는 `AgentState` 스키마(`command`, `plan`, `history` 등)만 사용됨

### 시나리오 C — Human Gateway 강제 진입 검증

1. 테스트용으로 `max_retries=0` 또는 `EvaluatorService.evaluate()` 실패 고정(mock/patch) 조건으로 실행
2. 기대 결과
   - `human_gateway_node`로 라우팅되고 `input()` 프롬프트가 출력됨
   - `exit` 입력 시 `done=True`로 종료

### 시나리오 D — 예외/실패 시 리소스 정리 검증

1. 실행 중 의도적으로 실패 유발(잘못된 셀렉터/네트워크 단절 등)
2. 기대 결과
   - 실패 후에도 `finally` 경로에서 `browser.close()`가 호출됨
   - 프로세스가 hang 없이 종료

## 산출물

- 신규: `surfy/state.py`, `surfy/graph.py`, `surfy/__main__.py`
- 수정: `main.py` (루트)

## 참고

- 본 계획은 이슈를 “기조”로만 참고하고, 객체/변수명은 현재 코드베이스 기준으로 재검토하여 반영한다.
- 핵심 목표는 LangGraph 도입과 Outer Loop의 안정적 오케스트레이션이다.
