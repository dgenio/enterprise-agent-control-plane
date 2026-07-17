.PHONY: help setup demo baseline test eval lint type coverage verify-trace docs-health traceability vibeguard vibeguard-domain

# Self-documenting help is the default goal (issue #164): `make` or `make help` lists every
# target with the `## description` annotation next to it.
.DEFAULT_GOAL := help

help: ## Show this help (the default target)
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install the package in editable mode (runtime dependencies: pydantic, pyyaml)
	python -m pip install -e .

demo: ## Run the baseline-vs-governed demo and refresh the trace/scorecard artifacts
	python -m apps.demo_cli.main

baseline: ## Run the unsafe baseline alone and refresh its trace artifact
	python -m apps.baseline_cli.main

test: ## Run the offline unit test suite
	python -m unittest discover -s tests -p "test_*.py" -v

eval: ## Run the offline router/policy evaluation regression gate
	python -m enterprise_agent_control_plane.evals

lint: ## Lint and format-check with ruff (needs .[dev]; issue #150)
	ruff check .
	ruff format --check .

type: ## Static type-check the package and scripts with mypy (needs .[dev]; issue #150)
	python -m mypy

coverage: ## Run the suite under coverage and print a missing-lines report (needs .[dev]; issue #175)
	coverage run -m unittest discover -s tests -p "test_*.py"
	coverage report

verify-trace: ## Verify a governed run's audit trace is schema-complete and tamper-evident (issue #201)
	python scripts/verify_trace.py

docs-health: ## Check internal doc links, canonical description, and version consistency
	python scripts/check_docs_health.py

traceability: ## Validate the control traceability matrix
	python scripts/check_traceability.py

vibeguard: ## Run the official VibeGuard artifact-hygiene gate (needs .[dev])
	vibeguard gate --fail-on high

vibeguard-domain: ## Run the repo-specific VibeGuard domain-gate self-check
	python scripts/vibeguard_gate.py --self-check
