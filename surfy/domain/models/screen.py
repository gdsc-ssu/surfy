from pydantic import BaseModel


class PageState(BaseModel):
    url: str
    title: str
    dom_text: str
    screenshot: str | None = None