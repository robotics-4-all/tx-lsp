.PHONY: lint format test build ci clean

lint:
	ruff check tx_lsp/
	ruff format --check tx_lsp/
	pylint tx_lsp/ --fail-under=8.0

format:
	ruff format tx_lsp/

test:
	pytest --cov=tx_lsp --cov-report=term-missing -v

build:
	python -m build --sdist --wheel

ci: lint test build

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
