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
.PHONY: test-unit
test-unit:
	@echo "[make] Running unit tests..."
	pytest --skip-integration --skip-doctest

# Run integration tests only
.PHONY: test-integration
test-integration:
	@echo "[make] Running integration tests..."
	pytest --skip-unit --skip-doctest

# Run doctests only
.PHONY: test-docstests
test-docstests:
	@echo "[make] Running doctests..."
	pytest --skip-unit --skip-integration

# Run all tests
.PHONY: test
test:
	@echo "[make] Running unit and integration tests..."
	pytest

# Lint and typecheck the code
.PHONY: lint
lint:
	@echo "[make] Linting and typechecking the code..."
	ruff check checker tests
	mypy checker
	black --check checker tests
	isort --check-only checker tests

# Format the code with black and isort
.PHONY: format
format:
	@echo "[make] Formatting the code..."
	black checker tests
	isort checker tests

# Deploy the documentation
.PHONY: docs-deploy
docs-deploy:
	@echo "[make] Deploying the documentation..."
	python -m mike deploy -b gh-pages `cat VERSION` --push
	python -m mike set-default `cat VERSION`

# Build the documentation
.PHONY: docs-build
docs-build:
	@echo "[make] Building the documentation..."
	python -m mkdocs build

# Serve the documentation in development mode
.PHONY: docs-serve
docs-serve:
	@echo "[make] Serve the documentation..."
	python -m mkdocs serve
