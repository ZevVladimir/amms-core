# Set make alone to just list the options from the Makefile
.DEFAULT_GOAL := help

# Shared with env/bootstrap.sh and env/activate.sh using one variable
AMMS_VENV ?= $(HOME)/.venvs/amms
export AMMS_VENV
PY := $(AMMS_VENV)/bin/python

.PHONY: help dev test lint fmt check clean

help: ## lists the targets
	@awk -F'##' '/^[a-z][a-z-]*:.*##/ {split($$1, a, ":"); printf " %-7s %s\n", a[1], $$2}' \
		$(MAKEFILE_LIST)

dev: ## create/refresh the venv, install editable + dev extras, install the hooks
	./env/bootstrap.sh

test: ## Run the full test suite
	$(PY) -m pytest

lint: ## Run the ruff format + autofix
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

fmt: ## Run the ruff format + autofix
	$(PY) -m ruff format . && $(PY) -m ruff check --fix .

check: lint test ## exactly what CI runs

clean: ## drop caches and build artifacts as well
	rm -rf build dist .pytest_cache .ruff_cache src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
