from __future__ import annotations

import logging

from surfy.domain.models.research import ResearchResult
from surfy.domain.models.route import RouteMap
from surfy.domain.ports.scout import ScoutPort

logger = logging.getLogger(__name__)


class ScoutService:
    def __init__(self, scout: ScoutPort):
        self._scout = scout

    async def scout(
        self,
        command: str,
        max_steps: int = 20,
        research_result: ResearchResult | None = None,
    ) -> RouteMap:
        try:
            task_prompt = f"정찰: {command}"
            if research_result and research_result.sources:
                urls_text = "\n".join(f"- {url}" for url in research_result.sources[:8])
                task_prompt += f"\n\n## 사전 조사에서 확인된 출처 URL (반드시 우선 방문)\n{urls_text}"
            if research_result and research_result.summary:
                task_prompt += f"\n\n## 사전 조사 요약\n{research_result.summary[:1000]}"

            route_map = await self._scout.explore(task=task_prompt, max_steps=max_steps)
            logger.info(
                "Scout completed: %d steps, final_url=%s",
                len(route_map.steps),
                route_map.final_url,
            )
            return route_map
        except Exception as e:
            logger.warning("Scout Agent failed: %s. Returning empty RouteMap.", e)
            return RouteMap(steps=[], final_url="", scout_summary=f"Scout failed: {e}")
