# Surfy

Hierarchical browser automation agent with Plan Anchor.

## Quick Start

### 사전 요구사항

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Chrome (CDP 연결용)

### 설치

```bash
# 1. 저장소 클론
git clone https://github.com/gdsc-ssu/surfy.git
cd surfy

# 2. 의존성 설치
uv sync

# 3. 로컬 패키지 editable 설치
uv pip install -e .

# 4. 환경 변수 설정
cp .env.example .env
# .env 파일에 ANTHROPIC_API_KEY 입력
```

### 실행

```bash
# Chrome을 CDP 모드로 실행 (별도 터미널)
# macOS:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux:
google-chrome --remote-debugging-port=9222

# surfy 실행
uv run python main.py "네이버에서 오늘 날씨 검색"
```

### 개발 도구

```bash
# lint
make lint

# 타입 체크
make typecheck

# lint + 타입 체크
make check
```

## Architecture

Hexagonal Architecture + Hierarchical Agent (Planner → Actor → Evaluator)

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

### Components

- **Planner**: 다음 1~2개 태스크만 생성 (rolling wave). DOM 안 봄. Plan Anchor로 첫 계획 품질 보장.
- **Actor**: 단일 태스크를 ReAct 루프로 실행. 매 스텝 DOM+Screenshot → LLM → 1 action → 실행 → 관찰.
- **Evaluator**: 구조화된 success criteria 체크 먼저, 애매하면 LLM 호출.

### Directory Structure

```
surfy/
├── domain/
│   ├── models/      # 순수 도메인 모델 (Pydantic)
│   ├── ports/       # 인터페이스 (ABC)
│   └── services/    # Planner, Actor, Evaluator
├── adapters/
│   ├── browser/     # browser-use 래핑
│   ├── llm/         # langchain-anthropic 래핑
│   └── human/       # CLI 입출력
├── graph.py         # LangGraph 상태머신
├── state.py         # AgentState
└── main.py          # Composition root
```

자세한 설계는 [`docs/0-initial-plan.md`](docs/0-initial-plan.md) 참조.

## Contributing

[Project Board](https://github.com/orgs/gdsc-ssu/projects/11)에서 이슈를 확인하세요.

1. `good-first-issue` 라벨이 붙은 이슈부터 시작
2. 이슈에서 브랜치 생성 → 작업 → PR
3. PR은 반드시 관련 이슈 번호 참조 (`closes #N`)