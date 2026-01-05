.PHONY: install lint format test check clean

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
