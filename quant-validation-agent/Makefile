# Makefile — quant-validation-agent
#
# Convenience targets for local dev and CI. Every target runs from the
# project root and stays read-only / local-file-only. No git push, no
# external API calls, no operational data access.
#
# Usage:
#   make test         # full pytest suite (incl. opt-in skipped)
#   make test-strict  # same suite with manifest+lock invariants enabled
#   make governance   # policy-governance audit (manifest + lock digest)
#   make smoke        # quick smoke runs over the example datasets
#   make ci           # test + governance + smoke (CI default)

PYTHON ?= python
PKG ?= quant_validation_agent

.PHONY: help test test-strict governance smoke smoke-scoring smoke-pd smoke-lgd smoke-ead smoke-scenario report-smoke ci clean

help:
	@echo "Targets:"
	@echo "  test          Full pytest suite"
	@echo "  test-strict   pytest with strict env vars (manifest + lock)"
	@echo "  governance    policy-governance audit"
	@echo "  smoke         Run validate* over examples/"
	@echo "  ci            test + governance + smoke"
	@echo "  clean         Remove __pycache__ and stray artifacts"

test:
	$(PYTHON) -m pytest

test-strict:
	QVA_STRICT_MANIFEST=1 QVA_STRICT_POLICY_LOCK=1 $(PYTHON) -m pytest

governance:
	$(PYTHON) -m $(PKG) policy-governance --json-only

smoke: smoke-scoring smoke-pd smoke-lgd smoke-ead smoke-scenario report-smoke

smoke-scoring:
	$(PYTHON) -m $(PKG) validate \
	    --data examples/sample_credit_score_data.csv \
	    --model-type scoring \
	    --target target --score score \
	    --decile-rag \
	    --out reports/_smoke_scoring.json

smoke-pd:
	$(PYTHON) -m $(PKG) validate-pd-calibration \
	    --data examples/sample_pd_timeseries.csv \
	    --pred-col predicted_pd --default-col defaults \
	    --count-col count --bucket-col grade \
	    --hl-bins 5 \
	    --out reports/_smoke_pd_calibration.json

smoke-lgd:
	$(PYTHON) -m $(PKG) validate \
	    --data examples/sample_lgd_ead_data.csv \
	    --model-type lgd \
	    --actual realized_lgd --predicted predicted_lgd \
	    --out reports/_smoke_lgd.json

smoke-ead:
	$(PYTHON) -m $(PKG) validate \
	    --data examples/sample_lgd_ead_data.csv \
	    --model-type ead \
	    --actual realized_ead --predicted predicted_ead \
	    --out reports/_smoke_ead.json

smoke-scenario:
	$(PYTHON) -m $(PKG) validate-scenario \
	    --hist-data examples/sample_macro_history.csv \
	    --scenario-data examples/sample_macro_scenario.csv \
	    --target pd_multiplier \
	    --features gdp_growth,unemployment,bond_spread \
	    --period-col period --pred-col-in-scenario pd_multiplier \
	    --multiplier-floors base=1.0,adverse=1.0,severe=1.0 \
	    --out reports/_smoke_scenario.json

report-smoke:
	$(PYTHON) -m $(PKG) report --input reports/_smoke_scoring.json --out reports/_smoke_scoring.md
	$(PYTHON) -m $(PKG) report --scenario-input reports/_smoke_scenario.json --include-stationarity-rag --out reports/_smoke_scenario.md

ci: test governance smoke

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -f reports/_smoke_*.json reports/_smoke_*.md
