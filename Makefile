.PHONY: fix lint typecheck test check serve stop restart chrome ext-build ext-dev

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
	doppler run -- uv run python main.py --serve --port 8765

stop:
	@lsof -ti:8765 2>/dev/null | xargs kill -9 2>/dev/null; echo "Stopped surfy server"

restart: stop
	@sleep 1
	@echo "Starting surfy server..."
	@doppler run -- uv run python main.py --serve --port 8765 &
	@sleep 2
	@lsof -i :8765 >/dev/null 2>&1 && echo "Surfy server running on :8765" || echo "Failed to start server"

chrome:
	@pkill -f "Google Chrome" 2>/dev/null; sleep 2; \
	open -a "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-cdp-profile; \
	sleep 2; \
	lsof -i :9222 >/dev/null 2>&1 && echo "Chrome CDP running on :9222" || echo "Failed to start Chrome CDP"

ext-build:
	cd extension && npm run build

ext-dev:
	cd extension && npm run dev
