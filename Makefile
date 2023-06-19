.PHONY: test lint

test:
	pdm run pytest -xl tests/

lint:
	pdm run ruff src/ tests && pdm run mypy src tests && pdm run black --check --quiet src tests && pdm run isort --check --quiet src tests
