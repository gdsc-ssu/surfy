.PHONY: lint typecheck check

lint:
	uv run ruff check surfy/

typecheck:
	uv run pyright surfy/

check: lint typecheck
