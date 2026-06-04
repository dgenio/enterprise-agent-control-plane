.PHONY: setup demo test

setup:
	python -m pip install -e .

demo:
	python -m apps.demo_cli.main

test:
	python -m unittest discover -s tests -p "test_*.py" -v
