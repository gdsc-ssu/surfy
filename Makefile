.PHONY: fix lint typecheck test check

fix:
	uv run ruff check --fix surfy/ tests/
	uv run ruff format surfy/ tests/

lint:
	uv run ruff check surfy/ tests/

typecheck:
	uv run pyright surfy/

test:
	uv run pytest tests/ -v --ignore=tests/test_phase1_integration.py

check: lint typecheck test
