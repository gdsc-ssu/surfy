import asyncio
import base64
import logging
import os
import sys
import re
from pathlib import Path

# 현재 파일 위치: surfy/surfy/scripts/test_phase1.py
# 프로젝트 루트(surfy/)를 sys.path에 추가하기 위해 상위 디렉토리로 3번 이동 (../../..)
current_file_path = Path(__file__).resolve()
project_root = current_file_path.parent.parent.parent
sys.path.append(str(project_root))

from surfy.adapters.browser.browser_use_adapter import BrowserUseAdapter
from surfy.domain.models import ActionType, BrowserAction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_element_id_by_attr(dom_text: str, attr_snippet: str) -> int | None:
    """
    DOM 텍스트에서 특정 속성 문자열을 포함하는 요소의 ID를 찾습니다.
    browser-use DOM 형식 예: [34] <input ... aria-label="Search" ...>
    """
    snippet_lower = attr_snippet.lower()
    for line in dom_text.split('\n'):
        if snippet_lower in line.lower():
            match = re.search(r'\[(\d+)\]', line)
            if match:
                return int(match.group(1))
    return None

async def main():
    adapter = BrowserUseAdapter()
    cdp_url = "http://localhost:9222"
    
    print(f"--- [1] 브라우저 연결 시도: {cdp_url} ---")
    try:
        await adapter.connect(cdp_url)
        print("✅ 연결 성공")

        print("\n--- [2] 페이지 이동: Google ---")
        nav_result = await adapter.execute_action(
            BrowserAction(action_type=ActionType.GO_TO_URL, value="https://www.google.com")
        )
        print(f"이동 결과: {nav_result.success}, 메시지: {nav_result.message}")

        print("\n--- [3] 상태 조회 및 검색창 탐색 ---")
        state = await adapter.get_page_state()
        print(f"URL: {state.url}")
        print(f"Title: {state.title}")

        # # 디버깅용 DOM 확인 
        # print("\n--- DOM Preview ---")
        # print(state.dom_text[:2000])
        # print("--- END DOM Preview ---")

        # Google 검색창 찾기 (aria-label="Search" 또는 "검색")
        # 페이지 언어 설정에 따라 다를 수 있으므로 몇 가지 후보 확인
        candidates = [
            'name=q',              # 최고 우선순위
            'aria-label=검색',
            'aria-label="검색"',
            'title=검색',
            'aria-label="Search"',
        ]

        target_id = None
        for snippet in candidates:
            target_id = find_element_id_by_attr(state.dom_text, snippet)
            if target_id:
                print(f"✅ 검색창 요소 ID 발견 (snippet: '{snippet}'): {target_id}")
                break
        
        if target_id:
            print(f"✅ 검색창 요소 ID 발견: {target_id}")
            
            print(f"\n--- [4] 액션 테스트: 클릭 & 입력 (ID: {target_id}) ---")
            # 1. 클릭
            await adapter.execute_action(
                BrowserAction(action_type=ActionType.CLICK, target_id=target_id)
            )
            print("✅ Click 실행 완료")
            
            # 2. 텍스트 입력
            type_result = await adapter.execute_action(
                BrowserAction(action_type=ActionType.TYPE, target_id=target_id, value="Surfy Agent Test")
            )
            print(f"✅ Type 실행 결과: {type_result.success}")
            
            # 상태 업데이트 확인
            state = type_result.page_state or await adapter.get_page_state()

            print("\n--- [4-B] 추가 액션 테스트 (SCROLL, SEND_KEYS, DONE, STUCK, GO_BACK) ---")
            
            # 1. SCROLL_DOWN
            print(">> SCROLL_DOWN 실행")
            scroll_down_res = await adapter.execute_action(BrowserAction(action_type=ActionType.SCROLL_DOWN))
            print(f"   결과: {scroll_down_res.success}, 메시지: {scroll_down_res.message}")
            await asyncio.sleep(0.5)

            # 2. SCROLL_UP
            print(">> SCROLL_UP 실행")
            scroll_up_res = await adapter.execute_action(BrowserAction(action_type=ActionType.SCROLL_UP))
            print(f"   결과: {scroll_up_res.success}, 메시지: {scroll_up_res.message}")
            await asyncio.sleep(0.5)

            # 3. SEND_KEYS
            print(">> SEND_KEYS ('Enter') - 검색 실행")
            send_keys_res = await adapter.execute_action(BrowserAction(action_type=ActionType.SEND_KEYS, target_id=target_id, value="Enter"))
            print(f"   결과: {send_keys_res.success}, 메시지: {send_keys_res.message}")
            await asyncio.sleep(2)  # 검색 결과 로딩 대기

            print(">> SEND_KEYS ('Escape') - 검색 실행")
            send_keys_res = await adapter.execute_action(BrowserAction(action_type=ActionType.SEND_KEYS, target_id=target_id, value="Escape"))
            print(f"   결과: {send_keys_res.success}, 메시지: {send_keys_res.message}")
            await asyncio.sleep(2)  # 검색 결과 로딩 대기

            print(">> SEND_KEYS ('Tab') - 검색 실행")
            send_keys_res = await adapter.execute_action(BrowserAction(action_type=ActionType.SEND_KEYS, target_id=target_id, value="Tab"))
            print(f"   결과: {send_keys_res.success}, 메시지: {send_keys_res.message}")
            await asyncio.sleep(2)  # 검색 결과 로딩 대기

            # 4. DONE
            print(">> DONE (태스크 완료 신호 테스트)")
            res_done = await adapter.execute_action(BrowserAction(action_type=ActionType.DONE))
            print(f"   결과: {res_done.success}, 메시지: {res_done.message}")

            # 5. STUCK
            print(">> STUCK (에이전트 중단 신호 테스트)")
            res_stuck = await adapter.execute_action(BrowserAction(action_type=ActionType.STUCK))
            print(f"   결과: {res_stuck.success}, 메시지: {res_stuck.message}")

            # 6. GO_BACK
            print(">> GO_BACK (이전 페이지로 이동)")
            go_back_res = await adapter.execute_action(BrowserAction(action_type=ActionType.GO_BACK))
            print(f"   결과: {go_back_res.success}, 메시지: {go_back_res.message}")
            
            # 상태 갱신 (GO_BACK 후)
            state = await adapter.get_page_state()
            print(f"   현재 URL (뒤로가기 후): {state.url}")

        else:
            print("⚠️ 검색창 요소를 찾을 수 없어 액션 테스트를 건너뜁니다.")
            print(f"DOM 미리보기:\n{state.dom_text[:500]}...")

        print("\n--- [5] 스크린샷 저장 ---")
        if state.screenshot:
            # 프로젝트 루트의 screenshots 폴더에 저장
            output_dir = project_root / "surfy" / "scripts" / "screenshots"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / "phase1_test.png"
            
            img_data = base64.b64decode(state.screenshot)
            output_path.write_bytes(img_data)
            print(f"✅ 스크린샷 저장 완료: {output_path.absolute()}")

    finally:
        await adapter.close()
        print("\n--- [종료] 브라우저 세션 닫힘 ---")

if __name__ == "__main__":
    asyncio.run(main())