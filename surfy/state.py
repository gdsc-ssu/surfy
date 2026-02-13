import operator
from typing import Annotated, TypedDict

from surfy.models.execution import ExecutionResult
from surfy.models.macro import MacroPlan
from surfy.models.micro import MicroPlan
from surfy.models.review import ReviewResult
from surfy.models.screen import ScreenState


class AgentState(TypedDict, total=False):
    """LangGraph 상태 정의.

    - 기본 필드: 노드가 반환하면 값을 덮어씀
    - Annotated[..., operator.add]: 노드가 반환하면 기존 리스트에 append
    """
    user_command: str

    # Plans
    macro_plan: MacroPlan | None
    current_micro_plan: MicroPlan | None

    # Screen
    current_screen: ScreenState | None

    # Results
    last_execution_result: ExecutionResult | None
    last_review_result: ReviewResult | None

    # History (append-only)
    execution_history: Annotated[list[ExecutionResult], operator.add]
    review_history: Annotated[list[ReviewResult], operator.add]

    # Retry counters
    micro_retry_count: int
    macro_retry_count: int
    max_micro_retries: int
    max_macro_retries: int

    # Control flags
    needs_human_intervention: bool
    is_complete: bool