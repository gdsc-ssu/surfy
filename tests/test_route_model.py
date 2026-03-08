"""RouteMap 및 RouteStep 모델 단위 테스트."""

from surfy.domain.models import RouteMap, RouteStep


def test_route_step_creation():
    """RouteStep 생성 및 필드 검증."""
    step = RouteStep(
        url="https://example.com",
        title="Example",
        action_taken="CLICK(button1)",
        observed_elements=["button1", "input1"],
        notes="Found search bar",
    )
    assert step.url == "https://example.com"
    assert step.title == "Example"
    assert step.action_taken == "CLICK(button1)"
    assert step.observed_elements == ["button1", "input1"]
    assert step.notes == "Found search bar"


def test_route_map_creation():
    """RouteMap 생성 및 필드 검증."""
    step1 = RouteStep(
        url="https://example.com",
        title="Example",
        action_taken="GOTO",
        observed_elements=[],
        notes="Start",
    )
    step2 = RouteStep(
        url="https://example.com/search",
        title="Search",
        action_taken="TYPE(query)",
        observed_elements=["results"],
        notes="Searching",
    )
    
    route_map = RouteMap(
        steps=[step1, step2],
        final_url="https://example.com/search",
        scout_summary="Successfully found search results",
    )
    
    assert len(route_map.steps) == 2
    assert route_map.steps[0].url == "https://example.com"
    assert route_map.final_url == "https://example.com/search"
    assert route_map.scout_summary == "Successfully found search results"


def test_route_map_empty_steps():
    """빈 steps를 가진 RouteMap 생성."""
    route_map = RouteMap(
        steps=[],
        final_url="",
        scout_summary="No steps taken",
    )
    assert route_map.steps == []
    assert route_map.final_url == ""
    assert route_map.scout_summary == "No steps taken"


def test_route_map_serialization():
    """RouteMap JSON 직렬화 및 역직렬화 검증."""
    step = RouteStep(
        url="https://example.com",
        title="Example",
        action_taken="CLICK",
        observed_elements=["el1"],
        notes="note",
    )
    route_map = RouteMap(
        steps=[step],
        final_url="https://example.com",
        scout_summary="summary",
    )
    
    json_data = route_map.model_dump_json()
    assert "https://example.com" in json_data
    assert "summary" in json_data
    
    # 역직렬화
    parsed = RouteMap.model_validate_json(json_data)
    assert parsed.steps[0].url == step.url
    assert parsed.scout_summary == route_map.scout_summary
