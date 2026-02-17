# Multi-Review Plugin Makefile
#
# Usage:
#   make test          - Run tests with coverage
#   make bench-quick   - Run quick benchmark (subset of fixtures)
#   make bench-full    - Run full benchmark (all fixtures)
#   make check-gates   - Check benchmark results against gates
#   make lint          - Run linter (ruff)
#   make format        - Format code (ruff format)
#   make all           - Run test, lint, and quick benchmark

# Use uv consistently
VENV = uv run

# Directories
SCRIPTS_DIR = scripts
TESTS_DIR = tests
BENCHMARKS_DIR = benchmarks
RESULTS_DIR = $(BENCHMARKS_DIR)/results

# Default target
.PHONY: help
help:
	@echo "Multi-Review Plugin Commands:"
	@echo "  make test          - Run tests with coverage"
	@echo "  make bench-quick   - Run quick benchmark (subset)"
	@echo "  make bench-full    - Run full benchmark (all fixtures)"
	@echo "  make check-gates   - Check benchmark results against gates"
	@echo "  make lint          - Run linter (ruff)"
	@echo "  make format        - Format code (ruff format)"
	@echo "  make all           - Run test, lint, and quick benchmark"

# Run tests with coverage
.PHONY: test
test:
	$(VENV) pytest $(TESTS_DIR)/ --cov=$(SCRIPTS_DIR) --cov-report=term-missing --cov-report=xml:coverage.xml

# Run tests without coverage (faster)
.PHONY: test-fast
test-fast:
	$(VENV) pytest $(TESTS_DIR)/ -v --tb=short

# Run quick benchmark (specific fixtures, combined into single output)
.PHONY: bench-quick
bench-quick:
	@mkdir -p $(RESULTS_DIR)
	$(VENV) python $(SCRIPTS_DIR)/run_benchmark.py shell_strict_ok python_style_nitpick python_ruff_strict --output json --output-file $(RESULTS_DIR)/latest.json

# Run full benchmark (all fixtures)
.PHONY: bench-full
bench-full:
	@mkdir -p $(RESULTS_DIR)
	$(VENV) python $(SCRIPTS_DIR)/run_benchmark.py --output json --output-file $(RESULTS_DIR)/latest.json

# Check gates
.PHONY: check-gates
check-gates:
	$(VENV) python $(SCRIPTS_DIR)/check_gates.py $(RESULTS_DIR)/latest.json

# Run linter
.PHONY: lint
lint:
	$(VENV) ruff check $(SCRIPTS_DIR)/ $(TESTS_DIR)/

# Format code
.PHONY: format
format:
	$(VENV) ruff format $(SCRIPTS_DIR)/ $(TESTS_DIR)/

# Type check
.PHONY: typecheck
typecheck:
	$(VENV) mypy $(SCRIPTS_DIR)/ --ignore-missing-imports

# Run all checks (test + lint + quick benchmark + gates)
.PHONY: all
all: test lint bench-quick check-gates

# Clean generated files
.PHONY: clean
clean:
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -f coverage.xml .coverage
	rm -rf $(RESULTS_DIR)/*.json

# Install development dependencies
.PHONY: install-dev
install-dev:
	uv sync --dev
