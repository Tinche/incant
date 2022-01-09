.PHONY: test

test:
	pytest -xl tests/

lint:
	black --check --quiet src tests && isort --check --quiet src tests && flake8 src tests