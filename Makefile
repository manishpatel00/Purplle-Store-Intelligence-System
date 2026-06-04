# Makefile for Purplle Store Intelligence System

.PHONY: up down local-api demo test lint typecheck coverage replay validate weights check clean setup-data ingest-events test-group-entry test-api-schema test-edge-cases verify health metrics funnel anomalies quick-start

PYTHON ?= $(shell if [ -x .venv/bin/python3 ]; then echo .venv/bin/python3; elif [ -x venv/bin/python3 ]; then echo venv/bin/python3; else echo python3; fi)

## ============= SETUP & INFRASTRUCTURE =============

## Link Store 1/2 clips and POS CSV into data/
setup-data:
	bash scripts/setup_data.sh

## Run API locally with SQLite (no Docker)
local-api:
	bash scripts/local-api.sh

## Replay fixtures and smoke-test API + assertions
demo:
	bash scripts/demo.sh

## Ingest pre-generated CCTV JSONL into running API
ingest-events:
	bash scripts/ingest_jsonl.sh

## Start all services (Database + API + Redis + Dashboard)
up:
	docker compose up --build -d

## Stop all services and clean volumes
down:
	docker compose down -v

## ============= TESTING & QUALITY =============

## Run all tests (no GPU or real videos required)
test:
	$(PYTHON) -m pytest tests/ -m "not integration" -v

## Run group entry detection tests
test-group-entry:
	$(PYTHON) -m pytest tests/test_group_entry_detection.py -v --cov=pipeline.sessions --cov=pipeline.emit

## Run API schema validation tests
test-api-schema:
	$(PYTHON) -m pytest tests/test_api_schema_validation.py -v

## Run edge case tests (empty store, all-staff, zero purchases)
test-edge-cases:
	$(PYTHON) -m pytest tests/ -k "empty_store or all_staff or zero_purchase" -v

## Run tests and output coverage reports
coverage:
	$(PYTHON) -m pytest tests/ -m "not integration" --cov-report=term-missing --cov-report=html --cov=app --cov=pipeline
	@echo "Coverage report available in htmlcov/index.html"
	@echo "Minimum coverage target: 70%"

## Format and lint using Ruff
lint:
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m ruff format .

## Run typechecking using mypy
typecheck:
	$(PYTHON) -m mypy app/ pipeline/

## ============= PIPELINE & DATA =============

## Validate a JSONL event stream schema (usage: make validate JSONL=path/to/events.jsonl)
validate:
	$(PYTHON) -m pipeline.validate_schema $(JSONL)

## Replay JSONL events into the API in real time (usage: make replay JSONL=path/to/events.jsonl SPEED=5)
replay:
	$(PYTHON) -m pipeline.replay --jsonl $(JSONL) --speed $(or $(SPEED),5)

## Seed development/local DB with standard fixtures
seed:
	$(PYTHON) scripts/seed_fixtures.py

## Download YOLOv8s weights manually (CPU-only, ~22MB)
weights:
	$(PYTHON) -c "from ultralytics import YOLO; YOLO('yolov8s.pt')"
	@echo "Weights downloaded successfully."

## ============= VERIFICATION & LIVE TESTING =============

## Health check: curl /health endpoint with pretty JSON
health:
	@echo "Checking API health..."
	@curl -s http://localhost:8000/health | jq '.'

## Get metrics for a store (usage: make metrics STORE_ID=STORE_BLR_002)
metrics:
	@echo "Getting metrics for $(or $(STORE_ID),STORE_BLR_002)..."
	@curl -s http://localhost:8000/api/v1/stores/$(or $(STORE_ID),STORE_BLR_002)/metrics | jq '.'

## Get funnel conversion for a store (usage: make funnel STORE_ID=STORE_BLR_002)
funnel:
	@echo "Getting funnel for $(or $(STORE_ID),STORE_BLR_002)..."
	@curl -s http://localhost:8000/api/v1/stores/$(or $(STORE_ID),STORE_BLR_002)/funnel | jq '.funnel'

## Get active anomalies for a store (usage: make anomalies STORE_ID=STORE_BLR_002)
anomalies:
	@echo "Getting anomalies for $(or $(STORE_ID),STORE_BLR_002)..."
	@curl -s http://localhost:8000/api/v1/stores/$(or $(STORE_ID),STORE_BLR_002)/anomalies | jq '.active_anomalies'

## Quick start: up -> demo -> health check
quick-start: up
	@echo "⏳ Waiting for services to start (15s)..."
	@sleep 15
	@echo "🏥 Running health check..."
	@make health
	@echo ""
	@echo "🎯 Dashboard available at: http://localhost:5173"
	@echo "📊 API available at: http://localhost:8000/health"
	@echo ""
	@echo "Next steps:"
	@echo "1. Open http://localhost:5173 in browser"
	@echo "2. In another terminal: make replay JSONL=tests/fixtures/group_entry.jsonl SPEED=5"
	@echo "3. Watch metrics update in real-time"

## Pre-submission check: runs formatters, linters, typecheckers, and tests
check: lint typecheck test
	@echo "All quality checks passed successfully! ✅"

## Clean build/test caches
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov .coverage .mypy_cache .ruff_cache

