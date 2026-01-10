.PHONY: install dev test lint format typecheck clean db-migrate db-reset help

# Default target
help:
	@echo "AI Learning System - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install all dependencies"
	@echo "  make dev-setup   Install dependencies + pre-commit hooks"
	@echo ""
	@echo "Development:"
	@echo "  make dev         Run CLI in development mode"
	@echo "  make api         Run API server in development mode"
	@echo "  make test        Run all tests"
	@echo "  make test-unit   Run unit tests only"
	@echo "  make test-int    Run integration tests only"
	@echo "  make test-cov    Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint        Run linter (ruff)"
	@echo "  make format      Format code (black + ruff)"
	@echo "  make typecheck   Run type checker (mypy)"
	@echo "  make check       Run all checks (lint + typecheck + test)"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate  Run database migrations"
	@echo "  make db-reset    Reset database (WARNING: destroys data)"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean       Remove cache and build artifacts"

# Setup
install:
	poetry install

dev-setup: install
	poetry run pre-commit install

# Development
dev:
	poetry run learn --help

api:
	poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	poetry run pytest

test-unit:
	poetry run pytest tests/unit -v

test-int:
	poetry run pytest tests/integration -v

test-cov:
	poetry run pytest --cov=src --cov-report=html
	@echo "Coverage report generated in htmlcov/"

# Code Quality
lint:
	poetry run ruff check src tests

format:
	poetry run black src tests
	poetry run ruff check --fix src tests

typecheck:
	poetry run mypy src

check: lint typecheck test

# Database
db-migrate:
	@echo "Running migrations..."
	poetry run python -m src.shared.db.migrate

db-reset:
	@echo "WARNING: This will destroy all data!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	poetry run python -m src.shared.db.reset

# Utilities
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
