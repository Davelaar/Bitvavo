SHELL := /bin/bash

# Door te exporteren kun je `DOMAIN=... LE_EMAIL=... make deploy` doen
export DOMAIN ?= snapdiscounts.nl
export LE_EMAIL ?= r.davelaar@icloud.com

.PHONY: ci deploy logs status

ci:
	bash scripts/validate_infra.sh
	bash scripts/lint_terms.sh || true
	python scripts/validate_events.py

deploy: ci
	bash scripts/deploy.sh

logs:
	docker logs caddy --since=1m | tail -n +1 || true
	docker logs grafana --since=1m | tail -n +1 || true
	docker logs prometheus --since=1m | tail -n +1 || true

status:
	@echo "==> snapdiscounts.nl"
	curl -I https://snapdiscounts.nl/ | head -n1 || true
	curl -I https://snapdiscounts.nl/grafana/ | head -n1 || true
	curl -I https://snapdiscounts.nl/prometheus/-/ready | head -n1 || true
