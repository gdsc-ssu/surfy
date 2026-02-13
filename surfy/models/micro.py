from pydantic import BaseModel, Field

from surfy.models.enums import ActionType


class MicroAction(BaseModel):
    '''
        구체적으로 무엇을 어떻게 실행할지에 대한 객체
    '''
    action_type: ActionType = Field(description="실행할 액션 타입")
    target_index: int | None = Field(default=None, description="대상 DOM 요소 인덱스")
    value: str | None = Field(default=None, description="TYPE 등에 사용할 입력값")
    description: str = Field(default="", description="액션 설명")
    expected_outcome: str = Field(default="", description="액션 실행 후 기대 결과") # TODO: 이거가 그냥 단순히 str이어도 되는가?


class MicroPlan(BaseModel):
    '''
        하나의 MacroTask를 수행하기 위한 구체적 액션 계획
    '''
    macro_task_id: int = Field(description="이 MicroPlan이 속한 MacroTask의 task_id")
    actions: list[MicroAction] = Field(default_factory=list, description="실행할 액션 리스트")
    current_action_index: int = Field(default=0, description="현재 실행 중인 액션 인덱스")
    is_exception: bool = Field(default=False, description="예외 상태 감지 플래그")
    exception_reason: str = Field(default="", description="예외 사유")