.PHONY: install dev run test lint format worker sweeper

install:
	pip install -r requirements.txt

dev:
	python scripts/bootstrap_dev.py

run:
	python startup.py

test:
	pytest -q

lint:
	ruff check src tests

format:
	ruff format src tests

worker:
	python worker_startup.py

sweeper:
	python sweeper_startup.py
