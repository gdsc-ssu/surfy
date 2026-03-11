import logging

from surfy.domain.models.research import ResearchResult
from surfy.domain.ports.research import ResearchPort

logger = logging.getLogger(__name__)


class ResearcherService:
    """리서치 수행 서비스. ResearchPort에 위임한다."""

    def __init__(self, research_port: ResearchPort):
        self._research_port = research_port

    async def research(self, command: str) -> ResearchResult:
        """주어진 명령에 대해 리서치를 수행한다."""
        logger.info("Research 시작: %s", command[:50])
        result = await self._research_port.research(command)
        logger.info("Research 완료: %d sources", len(result.sources))
        return result
