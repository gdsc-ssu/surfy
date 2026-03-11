.PHONY: fix lint typecheck test check serve ext-build ext-dev stop

fix:
	uv run ruff check --fix surfy/ tests/
	uv run ruff format surfy/ tests/

lint:
	uv run ruff check surfy/ tests/

typecheck:
	uv run pyright surfy/

test:
	uv run pytest tests/ -v --ignore=tests/test_phase1_integration.py -m "not real"

check: lint typecheck test

serve:
	uv run python main.py --serve --port 8765

ext-build:
	cd extension && npm run build

ext-dev:
	cd extension && npm run dev

stop:
	@lsof -ti:8765 2>/dev/null | xargs kill -9 2>/dev/null; echo "Stopped surfy server"
