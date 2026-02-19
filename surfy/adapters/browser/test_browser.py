import asyncio
import base64
import logging
import os
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가하여 surfy 패키지를 찾을 수 있게 함
sys.path.append(os.getcwd())

from surfy.adapters.browser.browser_use_adapter import BrowserUseAdapter
from surfy.domain.models import ActionType, BrowserAction

logging.basicConfig(level=logging.INFO)

async def main():
    # 1. 어댑터 초기화
    adapter = BrowserUseAdapter()
    
    # 사전 준비: Chrome이 --remote-debugging-port=9222 로 실행 중이어야 합니다.
    cdp_url = "http://localhost:9222"
    
    print(f"--- [시작] {cdp_url} 연결 시도 ---")
    try:
        # 2. 연결 테스트
        await adapter.connect(cdp_url)
        print("연결 성공!")

        # 3. 페이지 이동 테스트
        print("\n--- [액션] Google로 이동 ---")
        nav_action = BrowserAction(action_type=ActionType.GO_TO_URL, value="https://www.google.com")
        result = await adapter.execute_action(nav_action)
        print(f"결과: {result.success}, 메시지: {result.message}")

        # 4. 상태 추출 테스트
        print("\n--- [상태] 페이지 정보 추출 ---")
        state = await adapter.get_page_state()
        print(f"URL: {state.url}")
        print(f"Title: {state.title}")
        print(f"DOM 텍스트 길이: {len(state.dom_text)}")
        print(f"DOM 미리보기: {state.dom_text[:200]}...")

        # 5. 스크린샷 저장 테스트
        if state.screenshot:
            screenshot_path = Path("./surfy/adapters/browser/test/test_screenshot.png")
            # browser-use는 보통 base64 문자열을 반환하므로 bytes로 변환이 필요할 수 있음
            content = state.screenshot
            if isinstance(content, str):
                content = base64.b64decode(content)
            screenshot_path.write_bytes(content)
            print(f"스크린샷 저장 완료: {screenshot_path.absolute()}")

        # 6. 텍스트 가시성 테스트
        print("\n--- [검증] 'Google' 텍스트 가시성 확인 ---")
        is_visible = await adapter.check_text_visible("Google")
        print(f"'Google' 문구가 보이나요? {is_visible}")

    except Exception as e:
        print(f"\n[오류] 테스트 중 실패 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 7. 종료
        await adapter.close()
        print("\n--- [종료] 브라우저 세션 닫힘 ---")

if __name__ == "__main__":
    asyncio.run(main())