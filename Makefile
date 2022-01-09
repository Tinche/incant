.PHONY: test

test:
	pytest -xl tests/

lint:
	mypy src tests && black --check --quiet src tests && isort --check --quiet src tests && flake8 src tests