VENV := venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.DEFAULT_GOAL := help

.PHONY: help install run test lint audit clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## Create venv and install the app with dev tools
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

run:  ## Launch the menu-bar app
	$(VENV)/bin/thai-song-player

test:  ## Run unit tests
	$(VENV)/bin/pytest -v

lint:  ## Lint with ruff
	$(VENV)/bin/ruff check .

audit:  ## Scan dependencies for known vulnerabilities
	$(VENV)/bin/pip-audit

clean:  ## Remove venv, caches, and build artifacts
	rm -rf $(VENV) build dist *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
