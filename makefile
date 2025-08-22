install:
	poetry install

fmt:
	poetry run ruff format tests derive_action_signing examples
	poetry run ruff format --check tests derive_action_signing examples

lint:
	poetry run ruff check --fix tests derive_action_signing examples

test:
	poetry run pytest -vv

all: fmt lint test