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

.PHONY: help test test-strict governance smoke smoke-scoring smoke-pd smoke-lgd smoke-ead smoke-scenario report report-smoke stationarity-report verify ci clean clean-reports

help:
	@echo "Targets:"
	@echo "  test          Full pytest suite"
	@echo "  test-strict   pytest with strict env vars (manifest + lock)"
	@echo "  governance    policy-governance audit"
	@echo "  smoke         Run validate* over examples/"
	@echo "  report        Render every smoke output to a 9-section markdown"
	@echo "  stationarity-report  Render the scenario report with stationarity RAG"
	@echo "  verify        test + governance + summary (CI gate)"
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

# Public alias: run all four smoke validations and render every output to
# a 9-section markdown report. Depends on the smoke-* targets so JSON
# inputs exist before the renderer runs.
report: smoke-scoring smoke-pd smoke-lgd smoke-ead smoke-scenario
	$(PYTHON) -m $(PKG) report --input reports/_smoke_scoring.json --out reports/_smoke_scoring.md
	$(PYTHON) -m $(PKG) report --input reports/_smoke_pd_calibration.json --out reports/_smoke_pd_calibration.md
	$(PYTHON) -m $(PKG) report --input reports/_smoke_lgd.json --out reports/_smoke_lgd.md
	$(PYTHON) -m $(PKG) report --input reports/_smoke_ead.json --out reports/_smoke_ead.md
	$(PYTHON) -m $(PKG) report --scenario-input reports/_smoke_scenario.json --include-stationarity-rag --out reports/_smoke_scenario.md
	@echo "Rendered: reports/_smoke_*.md"

# Render only the scenario report with the stationarity RAG block enabled,
# without re-running every smoke target. Useful when reviewing macro
# scenario regressions in isolation.
stationarity-report: smoke-scenario
	$(PYTHON) -m $(PKG) report \
	    --scenario-input reports/_smoke_scenario.json \
	    --include-stationarity-rag \
	    --out reports/_smoke_scenario_stationarity.md
	@echo "Rendered: reports/_smoke_scenario_stationarity.md"

# Strict CI gate: run tests, audit policy governance with lock enforcement
# (use --exit-on-yellow for soft-fail), then aggregate every smoke output
# via the summary subcommand and fail on any Red.
verify: test governance smoke
	$(PYTHON) -m $(PKG) summary \
	    --input reports/_smoke_scoring.json \
	    --input reports/_smoke_pd_calibration.json \
	    --input reports/_smoke_lgd.json \
	    --input reports/_smoke_ead.json \
	    --input reports/_smoke_scenario.json \
	    --fail-on-red
	@echo "verify: OK"

ci: test governance smoke

# Removes only the smoke artifacts. Use this when you want to keep
# __pycache__ around for fast re-runs (cold start can be slow on Windows).
clean-reports:
	rm -f reports/_smoke_*.json reports/_smoke_*.md
	@echo "Removed smoke reports. docs/cli_reference.md preserved (regenerate via docs-cli)."

clean: clean-reports
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	@echo "Removed __pycache__ in addition to smoke reports."
