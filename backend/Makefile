.PHONY: help dev install test lint format clean docker-up docker-down setup ready

help:
	@echo "Available commands:"
	@echo "  make dev          - Start development server"
	@echo "  make install      - Install Python dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linter"
	@echo "  make format       - Format code"
	@echo "  make docker-up    - Start Docker services (postgres, redis)"
	@echo "  make docker-down  - Stop Docker services"
	@echo "  make setup        - One-button env setup (install deps, docker-compose up, port alignment)"
	@echo "  make ready        - Run readiness check (config, packages, DB, Redis)"
	@echo "  make clean        - Clean cache files"

setup:
	@bash scripts/setup_env.sh

ready:
	@poetry run python scripts/check_readiness.py

dev:
	@VENV_PATH=$$(poetry env info --path); \
	$$VENV_PATH/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

install:
	python3 -m pip install poetry && poetry install

install-requirements:
	python3 -m pip install -r requirements.txt

install-dev:
	python3 -m pip install -r requirements-dev.txt

test:
	poetry run pytest --asyncio-mode=auto

test-requirements:
	python3 -m pytest --asyncio-mode=auto

lint:
	poetry run ruff check app/
	poetry run black --check app/

lint-requirements:
	python3 -m ruff check app/
	python3 -m black --check app/

format:
	poetry run black app/
	poetry run ruff check --fix app/

format-requirements:
	python3 -m black app/
	python3 -m ruff check --fix app/

docker-up:
	cd .. && docker-compose up -d

docker-down:
	cd .. && docker-compose down

migrate:
	alembic upgrade head

migrate-create:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

clean:
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -r {} + 2>/dev/null || true
