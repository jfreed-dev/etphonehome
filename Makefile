.PHONY: install lint format test check clean web-build web-deploy dev

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Create virtual environment and install dependencies
install: $(VENV)/bin/activate

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install -e ".[server,dev]"

# Run linting checks (no modifications)
lint: install
	$(VENV)/bin/ruff check .
	$(VENV)/bin/black --check .

# Auto-format and fix lint issues
format: install
	$(VENV)/bin/black .
	$(VENV)/bin/ruff check --fix .

# Run tests
test: install
	$(VENV)/bin/pytest

# Run all checks (lint + test)
check: lint test

# Clean up
clean:
	rm -rf $(VENV)
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -rf .pytest_cache .ruff_cache
	rm -rf *.egg-info
	rm -rf web/build web/node_modules

# Build Svelte UI
web-build:
	cd web && npm install && npm run build

# Copy Svelte build to server for local testing
web-deploy: web-build
	rm -rf server/static/*
	cp -r web/build/* server/static/

# Run server with built UI (for local testing)
server: install web-deploy
	$(PYTHON) -m server.mcp_server --transport http --port 8765

# Development mode: Svelte dev server + Python backend
dev: install
	@echo "Starting Svelte dev server and Python backend..."
	@echo "Web UI: http://localhost:5173 (with HMR)"
	@echo "API: http://localhost:8765"
	cd web && npm run dev &
	$(PYTHON) -m server.mcp_server --transport http --port 8765
