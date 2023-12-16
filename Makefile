#.RECIPEPREFIX = >>
# Default task to run when no task is specified
all: help

# Help task to display callable targets
help:
	@echo "Makefile commands:"
	@echo "test-unit        - Run unit tests with pytest"
	@echo "test-integration - Run integration tests with pytest"
	@echo "test-docstests   - Run doctests with pytest"
	@echo "test             - Run all tests with pytest"
	@echo "lint             - Lint and typecheck the code"
	@echo "format           - Format the code with black"
	@echo "docs-build       - Build the documentation"
	@echo "docs-serve       - Serve the documentation in development mode"
	@echo "help             - Display this help"

# Run unit tests only
test-unit:
	@echo "[make] Running unit tests..."
	pytest --skip-integration --skip-doctest

# Run integration tests only
test-integration:
	@echo "[make] Running integration tests..."
	pytest --skip-unit --skip-doctest

# Run doctests only
test-docstests:
	@echo "[make] Running doctests..."
	pytest --skip-unit --skip-integration

# Run all tests
test:
	@echo "[make] Running unit and integration tests..."
	pytest

# Lint and typecheck the code
lint:
	@echo "[make] Linting and typechecking the code..."
	ruff check checker tests
	mypy checker tests
	black --check checker tests
	isort --check-only checker tests

# Format the code with black and isort
format:
	@echo "[make] Formatting the code..."
	black checker tests
	isort checker tests

# Build the documentation
docs-build:
	@echo "[make] Building the documentation..."
	mike deploy `cat VERSION`
	mike set-default `cat VERSION`

# Serve the documentation in development mode
docs-serve:
	@echo "[make] Serve the documentation..."
	mike deploy `cat VERSION`
	mike set-default `cat VERSION`
	mike serve


.PHONY: all help test-unit test-integration test-docstests test lint format docs-build docs-serve
