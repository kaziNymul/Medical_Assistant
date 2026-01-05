.PHONY: help install dev test lint format run docker-build docker-run clean

# Default target
help:
	@echo "AI Clinical Documentation Assistant"
	@echo ""
	@echo "Available commands:"
	@echo "  make install      Install production dependencies"
	@echo "  make dev          Install development dependencies"
	@echo "  make test         Run tests"
	@echo "  make lint         Run linting"
	@echo "  make format       Format code"
	@echo "  make run          Start the server"
	@echo "  make docker-build Build Docker image"
	@echo "  make docker-run   Run with Docker Compose"
	@echo "  make clean        Clean temporary files"

# Install production dependencies
install:
	pip install -r requirements.txt

# Install development dependencies
dev:
	pip install -e ".[dev]"

# Run tests
test:
	pytest -v --cov=src --cov-report=term-missing

# Run tests with HTML coverage report
test-cov:
	pytest -v --cov=src --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# Run linting
lint:
	ruff check src/ tests/
	mypy src/

# Format code
format:
	black src/ tests/
	ruff check --fix src/ tests/

# Run the development server
run:
	python -m src.main

# Run with uvicorn and auto-reload
run-dev:
	uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000

# Build Docker image
docker-build:
	docker build -t medical-assistant:latest .

# Run with Docker Compose
docker-run:
	docker-compose up -d

# Stop Docker containers
docker-stop:
	docker-compose down

# View Docker logs
docker-logs:
	docker-compose logs -f

# Ingest sample data
ingest-sample:
	curl -X POST http://localhost:8000/documents/ingest-sample

# Clean temporary files
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov .coverage
	rm -rf dist build *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Clean vector store (CAUTION: deletes indexed data)
clean-data:
	rm -rf data/vector_store/*
	@echo "Vector store cleared"

# Setup for new development
setup: install
	cp .env.example .env
	@echo "Setup complete. Edit .env if needed, then run: make run"
