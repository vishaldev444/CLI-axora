# Axora Makefile
.PHONY: install install-dev test lint format clean start stop status

VENV_DIR ?= $(HOME)/.axora/venv
PYTHON    ?= $(VENV_DIR)/bin/python
PIP       ?= $(VENV_DIR)/bin/pip
AXORA     ?= $(VENV_DIR)/bin/axora

install:
	bash install.sh

install-dev:
	bash install.sh --dev

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check axora/
	$(PYTHON) -m ruff format --check axora/

format:
	$(PYTHON) -m ruff format axora/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf dist/ build/ *.egg-info

# Dev shortcuts
start:
	$(AXORA) agent start --reload

stop:
	$(AXORA) agent stop

status:
	$(AXORA) status
