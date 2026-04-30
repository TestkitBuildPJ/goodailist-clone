.PHONY: install seed run test cov lint type check clean ci

PYTHON ?= python3

install:  ## Install package in editable mode + dev deps
	$(PYTHON) -m pip install -e ".[dev]"

seed:  ## Re-seed seed_data/repos.json into SQLite
	$(PYTHON) -m app.seed

run:  ## Run uvicorn dev server on :8000
	$(PYTHON) -m uvicorn app.main:app --reload --port 8000

test:  ## Run pytest
	$(PYTHON) -m pytest tests/ -v

cov:  ## Run coverage with 80% gate
	$(PYTHON) -m coverage run --source=app -m pytest tests/ -q
	$(PYTHON) -m coverage report --fail-under=80

lint:  ## Ruff check
	$(PYTHON) -m ruff check app/ tests/

type:  ## mypy --strict on app/
	$(PYTHON) -m mypy --strict app/

check: lint type cov  ## Run all quality gates locally (matches CI)

ci: check  ## Alias for `check`

clean:  ## Remove caches + SQLite db
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	rm -f goodailist.db
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

help:  ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'
