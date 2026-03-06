from pydantic import BaseModel


class Task(BaseModel):
    description: str
    # success_criteria는 Phase 3에서 추가
