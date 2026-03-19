import operator
from typing import Annotated, NotRequired, TypedDict

from surfy.domain.models import EvalResult, HistoryEntry, PageState, RouteMap, Task
from surfy.domain.models.plan import Plan
from surfy.domain.models.research import ResearchResult


class AgentState(TypedDict):
    command: str
    plan: Plan | None
    route_map: RouteMap | None
    current_task_idx: int
    eval_result: EvalResult | None
    retry_count: int
    max_retries: int
    history: Annotated[list[HistoryEntry], operator.add]
    completed_tasks: Annotated[list[Task], operator.add]
    last_page_state: PageState | None
    plan_approved: bool
    user_feedback: str | None
    research_result: ResearchResult | None
    report_result: NotRequired[str | None]
    auth_required: bool
    done: bool
    error: str | None
