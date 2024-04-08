.PHONY: test lint

test:
	pdm run pytest -xl tests/

lint:
	pdm run ruff check src/ tests && pdm run mypy src tests && pdm run black --check --quiet src tests
