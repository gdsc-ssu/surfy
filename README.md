# Surfy

Hierarchical browser automation agent with Plan Anchor.

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

### Key Design Decisions

- **browser-use** (v0.11) 활용: `BrowserStateSummary`, `SerializedDOMState.llm_representation()` 기반
- **Plan Anchor**: 불변 최종 목표(anchor) + rolling wave planning
- **Actor = simple while loop**: LangGraph는 외부 오케스트레이션에만 사용

### Directory Structure

```
surfy/
├── domain/
│   ├── models/      # 순수 도메인 모델
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

자세한 설계는 `docs/0-initial-plan.md` 참조.