"""Phase 1 통합 검증 — Chrome CDP 연결 + DOM + screenshot + 액션 실행.

실행: uv run pytest tests/test_phase1_integration.py -v
"""
import platform
import shutil
import subprocess
import tempfile
import time

import pytest
import pytest_asyncio

from surfy.adapters.browser.browser_use_adapter import BrowserUseAdapter
from surfy.domain.models import ActionType, BrowserAction

CDP_PORT = 9222


def _find_chrome() -> str:
    if platform.system() == "Darwin":
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return "google-chrome"


@pytest.fixture(scope="module")
def chrome():
    user_data_dir = tempfile.mkdtemp(prefix="surfy_test_")
    proc = subprocess.Popen(
        [
            _find_chrome(),
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)
    shutil.rmtree(user_data_dir, ignore_errors=True)


@pytest_asyncio.fixture()
async def adapter(chrome):
    a = await BrowserUseAdapter.create(f"http://localhost:{CDP_PORT}")
    yield a
    await a.close()


@pytest.mark.asyncio
async def test_go_to_url(adapter):
    result = await adapter.execute_action(
        BrowserAction(action_type=ActionType.GO_TO_URL, value="https://www.google.com")
    )
    assert result.success


@pytest.mark.asyncio
async def test_get_page_state(adapter):
    await adapter.execute_action(
        BrowserAction(action_type=ActionType.GO_TO_URL, value="https://www.google.com")
    )
    state = await adapter.get_page_state()
    assert "google" in state.url.lower()
    assert len(state.dom_text) > 0
    assert state.screenshot is not None


@pytest.mark.asyncio
async def test_check_text_visible(adapter):
    await adapter.execute_action(
        BrowserAction(action_type=ActionType.GO_TO_URL, value="https://www.google.com")
    )
    assert await adapter.check_text_visible("Google")