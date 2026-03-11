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

# 3. 환경 변수 설정
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

### 서버 모드 (Chrome Extension 연동)

```bash
# 1. 서버 시작
uv run python main.py --serve --port 8765

# 2. Extension 빌드
cd extension && npm install && npm run build

# 3. Chrome에서 Extension 로드
# chrome://extensions → 개발자 모드 → 압축해제된 확장 프로그램을 로드합니다 → extension/dist 선택
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
User Command (CLI or Extension)
    ↓
┌─ LangGraph Outer Loop ──────────────────────┐
│                                              │
│  Research → Scout → Planner → [Approval] → Actor → Evaluator
│                       ↑                              │
│                       └──── replan / next task ──────┘
│                                              │
└──────────────────────────────────────────────┘
    ↓                          ↑
  Done              WebSocket (server.py)
                         ↕
                  Chrome Extension
                  (Side Panel + Content Script)
```

### Components

- **Planner**: 다음 1~2개 태스크만 생성 (rolling wave). DOM 안 봄. Plan Anchor로 첫 계획 품질 보장.
- **Actor**: 단일 태스크를 ReAct 루프로 실행. 매 스텝 DOM+Screenshot → LLM → 1 action → 실행 → 관찰.
- **Evaluator**: 구조화된 success criteria 체크 먼저, 애매하면 LLM 호출.

### Directory Structure

```
surfy/
├── domain/
│   ├── models/      # 순수 도메인 모델 (Pydantic) + WebSocket 메시지 프로토콜
│   ├── ports/       # 인터페이스 (ABC)
│   └── services/    # Planner, Actor, Evaluator
├── adapters/
│   ├── browser/     # browser-use 래핑
│   ├── llm/         # langchain-anthropic 래핑
│   └── research/    # DdgsSearchAdapter
├── graph.py         # LangGraph 상태머신 (interrupt 기반 HITL)
├── state.py         # AgentState (user_feedback 포함)
├── server.py        # FastAPI WebSocket 서버
├── config.py        # Pydantic Settings
└── prompts/         # .prompty 템플릿 파일
extension/           # Chrome Extension MV3
├── src/
│   ├── sidepanel/   # React Side Panel (계획 시각화 + 채팅)
│   ├── offscreen/   # WebSocket 클라이언트
│   ├── background/  # Service Worker
│   └── content/     # DOM 하이라이트 Content Script
└── manifest.json
```

자세한 설계는 [`docs/0-initial-plan.md`](docs/0-initial-plan.md) 참조.

## Contributing

[Project Board](https://github.com/orgs/gdsc-ssu/projects/11)에서 이슈를 확인하세요.

1. `good-first-issue` 라벨이 붙은 이슈부터 시작
2. 이슈에서 브랜치 생성 → 작업 → PR
3. PR은 반드시 관련 이슈 번호 참조 (`closes #N`)