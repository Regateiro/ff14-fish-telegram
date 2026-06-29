.PHONY: install lint format typecheck test run clean

install:
	poetry install

lint:
	poetry run ruff check src/ tests/

format:
	poetry run ruff format src/ tests/

typecheck:
	poetry run python -m pip install mypy 2>/dev/null || true
	poetry run mypy src/ --ignore-missing-imports || true

test:
	poetry run pytest tests/ -v --cov=src/ff14_fish_telegram --cov-report=term-missing

run:
	poetry run python -m ff14_fish_telegram

clean:
	rm -rf *.db data_cache.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
