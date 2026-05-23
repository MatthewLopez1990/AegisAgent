.PHONY: test health audit tui web gateway

PYTHON ?= python3

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

health:
	PYTHONPATH=src $(PYTHON) -m aegisagent health

audit:
	PYTHONPATH=src $(PYTHON) -m aegisagent audit verify

tui:
	PYTHONPATH=src $(PYTHON) -m aegisagent tui

gateway:
	PYTHONPATH=src $(PYTHON) -m aegisagent gateway --host 127.0.0.1 --port 8787

web:
	PYTHONPATH=src $(PYTHON) -m aegisagent web --host 127.0.0.1 --port 8787
