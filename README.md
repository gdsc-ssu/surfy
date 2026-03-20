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
```

### 3. 환경 변수 설정

Surfy는 시크릿 관리를 위해 **Doppler** 사용을 권장합니다.

#### 옵션 A: Doppler 사용 (권장)

```bash
# 1. Doppler CLI 설치 (macOS)
brew install dopplerhq/cli/doppler

# 2. 로그인 및 프로젝트 설정
doppler login
doppler setup  # 자동으로 surfy 프로젝트의 dev 설정과 매핑됩니다
```
설정 후에는 `make serve` 등의 명령어가 자동으로 Doppler에서 시크릿을 가져와 주입합니다.

#### 옵션 B: .env 파일 사용 (Fallback)
Doppler 없이 로컬 환경 변수를 사용하려면 `.env` 파일을 생성합니다.
```bash
cp .env.example .env
```
`.env` 파일을 열어 아래 키들을 입력합니다:
- `ANTHROPIC_API_KEY`: [Anthropic Console](https://console.anthropic.com/)에서 발급
- `GOOGLE_API_KEY`: [Google AI Studio](https://aistudio.google.com/apikey)에서 발급 (권장)

> `GOOGLE_API_KEY`가 없으면 Scout도 Claude를 사용합니다 (동작하지만 느림).

### Chrome을 CDP 모드로 실행

Surfy는 사용자의 Chrome에 CDP(Chrome DevTools Protocol)로 연결하여 동작합니다.
**기존에 실행 중인 Chrome을 모두 닫고** 아래 명령으로 재시작해야 합니다.

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-cdp-profile

# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-cdp-profile

# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-cdp-profile"
```

> ⚠️ `--user-data-dir`을 지정하면 깨끗한 프로필로 시작됩니다 (로그인 세션 없음).
> 기본 프로필 사용은 Chrome 136+ 보안 정책으로 인해 현재 불가합니다. ([#39](https://github.com/gdsc-ssu/surfy/issues/39))

### 서버 + Extension으로 실행 (권장)

```bash
# 1. 서버 시작
uv run python main.py --serve --port 8765

# 2. Extension 빌드
cd extension && npm install && npm run build
cd ..
```

3. Chrome에서 Extension 로드:
   - 주소창에 `chrome://extensions` 입력
   - 우측 상단 **개발자 모드** 토글 ON
   - **압축해제된 확장 프로그램을 로드합니다** 클릭
   - `extension/dist` 폴더 선택
   - Extension 아이콘 클릭 → Side Panel 열림

4. Side Panel에서 명령 입력 (예: `네이버에서 오늘 날씨 검색`)

### CLI 모드 (Extension 없이)

```bash
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
│   └── research/    # GeminiGroundingAdapter
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

## Observability

LangGraph 노드 실행, LLM prompt/response, 상태 전이를 추적할 수 있습니다. 두 가지 옵션 중 선택하세요.

| | LangSmith (SaaS) | Langfuse (Self-hosted) |
|---|---|---|
| 비용 | Free 5,000 traces/month, 팀 초대 시 $39/user/month | 무료 (Docker로 직접 운영) |
| 설치 | 환경변수 3개 | Docker Compose + 환경변수 3개 |
| 팀 공유 | 유료 플랜 필요 | 무제한 사용자, 무료 |
| 적합한 경우 | 개인 개발, 빠른 시작 | 팀 QA/디버깅, 비용 제한 환경 |

### LangSmith

```bash
# .env에 추가
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_xxxx    # https://smith.langchain.com 에서 발급
LANGSMITH_PROJECT=surfy
```

대시보드: https://smith.langchain.com

### Langfuse (Self-hosted)

Docker가 필요합니다. PostgreSQL, ClickHouse, Redis, MinIO, Langfuse가 한 번에 올라갑니다.

**1단계: Langfuse 서버 실행**

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

모든 컨테이너가 healthy 상태가 될 때까지 30초 정도 걸립니다.

**2단계: 계정 생성 및 API 키 발급**

1. http://localhost:3000 접속
2. **Sign Up**을 클릭하여 계정 생성 (이메일, 비밀번호 자유롭게 설정)
3. Organization 이름 입력 (예: `surfy`)
4. Project 생성 (처음 사용하는 경우 Project가 없으면 새로운 Project를 먼저 생성해야 합니다.)
5. 로그인 후 좌측 하단 **Settings** -> **API Keys** -> **Create New API Key**
6. 생성된 **Public Key**와 **Secret Key**를 복사 (Secret Key는 이 시점에만 표시됨)

**3단계: .env에 키 등록**

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-xxxx    # 2단계에서 복사한 Public Key
LANGFUSE_SECRET_KEY=sk-lf-xxxx    # 2단계에서 복사한 Secret Key
LANGFUSE_BASE_URL=http://localhost:3000
```

**4단계: Surfy 서버 재시작**

```bash
uv run python main.py --serve --port 8765
```

서버 로그에 `Langfuse tracing enabled`가 출력되면 정상. 이후 에이전트 실행 시 자동으로 trace가 기록됩니다.

대시보드에서 확인: http://localhost:3000 -> Traces 탭

환경변수가 없으면 트레이싱이 비활성화되므로 기존 동작에 영향 없음. 팀원 초대는 Settings -> Members에서 무제한, 무료.

### LangGraph Studio

그래프 노드를 실시간 시각화하고 시간여행 디버깅이 가능합니다.

```bash
pip install "langgraph-cli[inmem]"
langgraph dev
# → http://127.0.0.1:8123
```

## Contributing

[Project Board](https://github.com/orgs/gdsc-ssu/projects/11)에서 이슈를 확인하세요.

1. `good-first-issue` 라벨이 붙은 이슈부터 시작
2. 이슈에서 브랜치 생성 → 작업 → PR
3. PR은 반드시 관련 이슈 번호 참조 (`closes #N`)