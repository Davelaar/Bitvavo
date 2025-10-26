.PHONY: ci lint validate schema
ci: validate lint schema
validate:
	bash scripts/validate_infra.sh
lint:
	bash scripts/lint_terms.sh
schema:
	python scripts/validate_events.py
