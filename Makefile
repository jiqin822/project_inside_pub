.PHONY: help dev install test lint format clean docker-up docker-down docker-up-db migrate

help:
	@echo "Available commands:"
	@echo "  make dev          - Start development server"
	@echo "  make install      - Install Python dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linter"
	@echo "  make format       - Format code"
	@echo "  make docker-up    - Start Docker services (postgres, redis, mysql, voiceprint-api)"
	@echo "  make docker-down  - Stop Docker services"
	@echo "  make docker-up-db  - Start only database services (postgres, redis, mysql)"
	@echo "  make migrate      - Run database migrations"
	@echo "  make clean        - Clean cache files"

dev:
	# Use this so TitaNet (NeMo) is available for speaker IDs; Poetry env has nemo_toolkit
	cd backend && poetry run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

install:
	cd backend && pip install poetry && poetry install

test:
	cd backend && poetry run pytest

lint:
	cd backend && poetry run ruff check app/
	cd backend && poetry run black --check app/

format:
	cd backend && poetry run black app/
	cd backend && poetry run ruff check --fix app/

docker-up:
	docker-compose up -d

docker-up-db:
	docker-compose up -d postgres redis mysql

docker-down:
	docker-compose down

migrate:
	cd backend && poetry run alembic upgrade head

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name ".ruff_cache" -exec rm -r {} +
