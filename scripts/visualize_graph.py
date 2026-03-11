"""LangGraph 그래프 시각화 — graph.png 생성.

사용법:
    uv run python scripts/visualize_graph.py
    uv run python scripts/visualize_graph.py --output my_graph.png
    uv run python scripts/visualize_graph.py --mermaid  # Mermaid 텍스트 출력
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

from surfy.graph import compile_graph


def _build_graph():
    """시각화 전용 — 더미 서비스로 그래프 구조만 컴파일."""
    return compile_graph(
        scout=MagicMock(),
        planner=MagicMock(),
        actor=MagicMock(),
        evaluator=MagicMock(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph 그래프 시각화")
    parser.add_argument("--output", "-o", default="graph.png", help="출력 파일 경로 (기본: graph.png)")
    parser.add_argument("--mermaid", action="store_true", help="Mermaid 텍스트만 출력")
    args = parser.parse_args()

    graph = _build_graph()
    drawable = graph.get_graph()

    if args.mermaid:
        print(drawable.draw_mermaid())
        return

    output_path = Path(args.output)
    png_bytes = drawable.draw_mermaid_png()
    output_path.write_bytes(png_bytes)
    print(f"그래프 저장 완료: {output_path.resolve()}")


if __name__ == "__main__":
    main()
