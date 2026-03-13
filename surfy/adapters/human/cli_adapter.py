import asyncio

from surfy.domain.ports import HumanPort


class CliAdapter(HumanPort): # HuanPort ABC 구현
    """터미널 입출력으로 사용자와 상호작용하는 어댑터."""

    async def ask(self, question: str) -> str:
        """사용자에게 질문하고 응답을 받음."""
        print(f"\n🤖 {question}")
        return await asyncio.to_thread(input, "👤 > ")

    async def notify(self, message: str) -> None:
        """사용자에게 상태 알림."""
        print(f"\nℹ️  {message}")
