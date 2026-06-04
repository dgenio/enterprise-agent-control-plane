.PHONY: setup demo test eval

setup:
	python -m pip install -e .

demo:
	python -m apps.demo_cli.main

test:
	python -m unittest discover -s tests -p "test_*.py" -v

eval:
	python -m enterprise_agent_control_plane.evals
