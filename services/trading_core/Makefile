.PHONY: venv run fmt

venv:
	python3 -m venv .venv && . .venv/bin/activate && pip install -r trading_core/requirements.txt

run:
	. .venv/bin/activate && python -m trading_core.main

fmt:
	@echo "Python files are small; consider black/ruff if needed."
