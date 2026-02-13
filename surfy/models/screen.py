from pydantic import BaseModel, Field


class DOMElement(BaseModel): # TODO: 이거 굳이 bs4 안쓰고 이렇게 하는 이유? 
    index: int = Field(description="DOM 요소의 고유 인덱스 번호")
    tag: str = Field(description="HTML 태그명")
    text: str = Field(default="", description="요소의 텍스트 내용")
    attributes: dict[str, str] = Field(default_factory=dict, description="HTML 속성")
    selector: str = Field(default="", description="CSS selector")
    is_visible: bool = Field(default=True, description="화면에 보이는지 여부")
    is_interactive: bool = Field(default=False, description="클릭/입력 가능 여부")


class ScreenState(BaseModel):
    url: str = Field(description="현재 페이지 URL")
    title: str = Field(default="", description="현재 페이지 타이틀")
    dom_elements: list[DOMElement] = Field(default_factory=list, description="파싱된 DOM 요소 리스트")
    screenshot_base64: str | None = Field(default=None, description="스크린샷 base64 인코딩")