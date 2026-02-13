from pydantic import BaseModel, Field

from surfy.models.enums import ExecutorType, TaskStatus


class MacroTask(BaseModel):
    '''
        Macro한 단계의 추상적인 해야할 일
    '''
    task_id: int = Field(description="태스크 순서 번호")
    description: str = Field(description="태스크 설명 (자연어)")
    executor: ExecutorType = Field(default=ExecutorType.AGENT, description="실행 주체")
    expected_outcome: str = Field(description="완료 판단 기준") # TODO: anchor가 단순히 이렇게 str형식이어도 되나?
    status: TaskStatus = Field(default=TaskStatus.NEW, description="태스크 상태")


class MacroPlan(BaseModel):
    '''
        유저가 원하는 단일 목표, MacroTask를 아우르는 객체
    '''
    anchor: str = Field(description="불변 최종 목표")
    tasks: list[MacroTask] = Field(default_factory=list, description="단계별 태스크 리스트")
    current_task_index: int = Field(default=0, description="현재 진행 중인 태스크 인덱스")
    replan_count: int = Field(default=0, description="재계획 횟수")