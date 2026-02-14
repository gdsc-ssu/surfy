# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## Team

| GitHub | 이름 | 학년 | 역할 |
|--------|------|------|------|
| @rover0811 | HyunSoo | Lead | 아키텍처, 코드 리뷰, issue 관리 |
| @kimseoungyun | KODE | 대3 | 주니어 (팀 내 상대적 시니어) |
| @hsung0714-bot | — | 대1 | 주니어 |
| @SeoYeongBaek | — | 대1 | 주니어 |

- 전원 e2e 프로젝트 경험 없는 주니어
- issue 작성 시 반드시 포함: 대상 파일 경로, 참고할 기존 코드/패턴, 명확한 완료 조건, 의존 issue 번호

## Issue Convention

- label: `phase-1` ~ `phase-5`, `good-first-issue` (주니어 온보딩용)
- issue body에 포함할 것:
  1. **배경**: 왜 이 작업이 필요한지
  2. **할 일**: 구체적 구현 내용
  3. **대상 파일**: 생성/수정할 파일 경로
  4. **완료 조건**: 검증 가능한 기준
  5. **의존성**: 선행 issue 번호 (있으면)
  6. **참고**: 관련 코드, 문서, 패턴