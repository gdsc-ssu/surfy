import asyncio
import sys
import logging
from surfy.graph import compile_graph


async def main():
    command = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("명령을 입력하세요: ")

    graph = compile_graph()
    initial_state = {
        "user_command": command,
        "macro_plan": None,
        "current_micro_plan": None,
        "current_screen": None,
        "last_execution_result": None,
        "last_review_result": None,
        "execution_history": [],
        "review_history": [],
        "micro_retry_count": 0,
        "macro_retry_count": 0,
        "max_micro_retries": 3,
        "max_macro_retries": 2,
        "needs_human_intervention": False,
        "is_complete": False,
    }

    async for event in graph.astream(initial_state):
        for node_name, update in event.items():
            print(f"[{node_name}] {update}")

    logging.info("작업이 완료되었습니다.")


if __name__ == "__main__":
    asyncio.run(main())