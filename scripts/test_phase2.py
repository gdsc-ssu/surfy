import asyncio
import logging
import platform
import subprocess
import time

from surfy.container import Container
from surfy.domain.models import Task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start_chrome_cdp(port: int = 9222) -> subprocess.Popen | None:
    """Start Chrome in CDP mode if not already running."""
    import socket

    # Check if already running
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            logger.info("Chrome CDP already running on port %d", port)
            return None

    # Start Chrome based on platform
    system = platform.system()
    if system == "Darwin":
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif system == "Linux":
        chrome_path = "google-chrome"
    elif system == "Windows":
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    logger.info("Starting Chrome in CDP mode...")
    process = subprocess.Popen(
        [
            chrome_path,
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--user-data-dir=/tmp/chrome-cdp-profile",
        ],
    )

    # Wait for Chrome to start
    for _ in range(10):
        time.sleep(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                logger.info("Chrome CDP started successfully")
                return process

    raise RuntimeError("Failed to start Chrome CDP")


async def main():
    chrome_process = start_chrome_cdp()

    try:
        container = Container()

        # 1. Chrome CDP 연결
        browser = await container.browser()

        try:
            # 2. Anthropic API 연결 (via DI)
            llm = container.llm()

            # 3. Actor 생성
            actor = container.actor_service(browser=browser, llm=llm)

            # 4. Task 정의 및 실행
            task = Task(
                description="코레일(korail.com)에 접속해서 내일 광명역에서 계룡역으로 가는 가장 빠른 기차편을 검색해주세요. 출발역: 광명, 도착역: 계룡, 날짜: 내일"
            )
            result = await actor.execute_task(task, max_steps=20)

            # 5. 결과 확인
            page_state = await browser.get_page_state()
            print(f"Final URL: {page_state.url}")
            print(f"Result: {result}")
        finally:
            await browser.close()
    finally:
        if chrome_process:
            logger.info("Terminating Chrome...")
            chrome_process.terminate()


if __name__ == "__main__":
    asyncio.run(main())
