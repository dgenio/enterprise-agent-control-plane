.PHONY: setup demo baseline test eval docs-health traceability vibeguard vibeguard-domain

setup:
	python -m pip install -e .

demo:
	python -m apps.demo_cli.main

baseline:
	python -m apps.baseline_cli.main

test:
	python -m unittest discover -s tests -p "test_*.py" -v

eval:
	python -m enterprise_agent_control_plane.evals

docs-health:
	python scripts/check_docs_health.py

traceability:
	python scripts/check_traceability.py

vibeguard:
	vibeguard gate --fail-on high

vibeguard-domain:
	python scripts/vibeguard_gate.py --self-check
