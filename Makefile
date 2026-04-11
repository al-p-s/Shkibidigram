.PHONY: help run dev build up down logs migrate makemigrations downgrade format lint

help:
	@echo "Available commands:"
	@echo "  make run            - Run app locally (without Docker)"
	@echo "  make dev            - Run app with auto-reload"
	@echo "  make build          - Build Docker image"
	@echo "  make up             - Start all services (Docker Compose)"
	@echo "  make down           - Stop all services"
	@echo "  make logs           - Tail app logs"
	@echo "  make migrate        - Apply all migrations"
	@echo "  make makemigrations - Generate new migration (msg='')"
	@echo "  make downgrade      - Rollback last migration"
	@echo "  make format         - Format code (black + isort)"
	@echo "  make lint           - Lint code (ruff)"

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f app

migrate:
	alembic upgrade head

makemigrations:
	alembic revision --autogenerate -m "$(msg)"

downgrade:
	alembic downgrade -1

format:
	black app && isort app

lint:
	ruff check app
