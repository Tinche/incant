test:
	uv run pytest -xl tests/

lint:
	uv run ruff check src/ tests && uv run mypy src tests && uv run black --check --quiet src tests
