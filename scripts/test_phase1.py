"""Phase 1 통합 테스트 스크립트

사전 조건:
    Chrome을 디버깅 모드로 실행해야 합니다:
    pkill -9 -f "Google Chrome"; sleep 2
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
        --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug-profile

실행:
    cd surfy
    .venv/bin/python scripts/test_phase1.py
"""

import asyncio
from pathlib import Path

from surfy.adapters.browser import BrowserUseAdapter
from surfy.domain.models import ActionType, BrowserAction


async def main() -> None:
    adapter = BrowserUseAdapter()

    # 1. CDP 연결
    print("=== 1. CDP 연결 ===")
    await adapter.connect("http://localhost:9222")
    print("연결 성공")

    # 2. Google로 이동
    print("\n=== 2. GO_TO_URL ===")
    result = await adapter.execute_action(
        BrowserAction(action_type=ActionType.GO_TO_URL, value="https://www.google.com")
    )
    print(f"결과: {result.success} - {result.message}")

    # 3. 페이지 상태 확인
    print("\n=== 3. get_page_state ===")
    state = await adapter.get_page_state()
    print(f"URL: {state.url}")
    print(f"Title: {state.title}")
    print(f"DOM text (첫 500자):\n{state.dom_text[:500]}")

    # 4. 스크린샷 저장
    print("\n=== 4. screenshot 저장 ===")
    if state.screenshot:
        out = Path(__file__).parent / "screenshot.png"
        out.write_bytes(state.screenshot)
        print(f"저장 완료: {out}  ({len(state.screenshot)} bytes)")
    else:
        print("screenshot 없음")

    # 5. TYPE — DOM에서 textarea index 자동 추출
    print("\n=== 5. TYPE ===")
    textarea_idx = None
    for line in state.dom_text.split("\n"):
        if "textarea" in line and "[" in line:
            textarea_idx = int(line.split("[")[1].split("]")[0])
            break

    if textarea_idx is None:
        print("textarea를 찾을 수 없음")
    else:
        print(f"textarea index: {textarea_idx}")
        result = await adapter.execute_action(
            BrowserAction(action_type=ActionType.TYPE, target_id=textarea_idx, value="hello world")
        )
        print(f"결과: {result.success} - {result.message}")

    # 6. CLICK — DOM 다시 읽고 검색 버튼 index 추출
    print("\n=== 6. CLICK ===")
    state = await adapter.get_page_state()
    btn_idx = None
    for line in state.dom_text.split("\n"):
        if "btnK" in line and "[" in line:
            btn_idx = int(line.split("[")[1].split("]")[0])
            break

    if btn_idx is None:
        print("검색 버튼을 찾을 수 없음")
    else:
        print(f"btnK index: {btn_idx}")
        result = await adapter.execute_action(
            BrowserAction(action_type=ActionType.CLICK, target_id=btn_idx)
        )
        print(f"결과: {result.success} - {result.message}")

    # 7. 최종 상태 확인
    print("\n=== 7. 최종 상태 ===")
    state = await adapter.get_page_state()
    print(f"URL: {state.url}")
    print(f"Title: {state.title}")

    # 8. check_text_visible
    print("\n=== 8. check_text_visible ===")
    visible = await adapter.check_text_visible("hello world")
    print(f"'hello world' 텍스트 존재: {visible}")

    await adapter.close()
    print("\n=== Phase 1 통합 테스트 완료 ===")


if __name__ == "__main__":
    asyncio.run(main())
