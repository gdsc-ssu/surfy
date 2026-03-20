from surfy.domain.models import Task
from surfy.domain.ports import LLMPort


class ReporterService:
    """완료된 태스크 결과를 종합하여 최종 보고를 생성하는 서비스."""

    def __init__(self, llm: LLMPort):
        self._llm = llm

    async def report(self, command: str, completed_tasks: list[Task]) -> str:
        """완료된 태스크들을 기반으로 최종 리포트를 생성한다."""
        task_results = [{"description": t.description, "result": t.result or "결과 없음"} for t in completed_tasks]
        try:
            return await self._llm.generate_report(command, task_results)
        except Exception:
            lines = [f"- {r['description']}: {r['result']}" for r in task_results]
            return "완료된 작업:\n" + "\n".join(lines)
