"""LangGraph Studio entry point.

`langgraph dev` 명령어로 Studio를 실행할 때 이 모듈의 `graph` 변수를 사용한다.
langgraph.json의 "graphs.surfy" 에서 참조됨.

사용법:
    pip install "langgraph-cli[inmem]"
    langgraph dev
"""
import logging

from browser_use import BrowserSession
from browser_use.llm import ChatAnthropic as BrowserUseChatAnthropic

from surfy.adapters.browser import BrowserUseAdapter
from surfy.adapters.browser.agent_adapter import BrowserUseAgentAdapter
from surfy.adapters.llm import AnthropicAdapter
from surfy.adapters.research import DdgsSearchAdapter
from surfy.domain.services import ActorService, EvaluatorService, PlannerService, ResearcherService, ScoutService
from surfy.graph import compile_graph

logging.basicConfig(level=logging.INFO, format="%(message)s")


def _make_graph():
    """서비스 인스턴스를 생성하고 그래프를 컴파일한다."""
    # BrowserUseAdapter는 내부적으로 session.start()가 필요하지만,
    # Studio 환경에서는 지연 연결되거나 별도 관리가 필요할 수 있음.
    # 여기서는 main.py의 구성을 따르되 동기적으로 초기화 가능한 부분만 처리.
    
    agent_session = BrowserSession(headless=False, disable_security=True)
    # Note: agent_session.start()는 코루틴이므로 모듈 수준에서 호출 불가.
    # BrowserUseAdapter와 BrowserUseAgentAdapter는 세션 객체를 주입받음.
    
    browser = BrowserUseAdapter(session=agent_session)
    llm = AnthropicAdapter(use_vision=True, model_name="claude-sonnet-4-20250514")
    agent_llm = BrowserUseChatAnthropic(model="claude-sonnet-4-20250514")

    agent_adapter = BrowserUseAgentAdapter(session=agent_session, llm=agent_llm)
    researcher = ResearcherService(research_port=DdgsSearchAdapter())

    planner = PlannerService(llm=llm)
    actor = ActorService(browser=browser, llm=llm)
    scout = ScoutService(agent_adapter=agent_adapter)
    evaluator = EvaluatorService(browser=browser, llm=llm)

    return compile_graph(
        scout=scout,
        planner=planner,
        actor=actor,
        evaluator=evaluator,
        researcher=researcher,
    )


graph = _make_graph()
