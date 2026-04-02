PYTHON ?= python
CLI = $(PYTHON) -m src.cli

.PHONY: bootstrap data-fetch research-all report paper-start demo-start live-start status pause resume kill test

bootstrap:
	$(CLI) bootstrap

data-fetch:
	$(CLI) data-fetch

research-all:
	$(CLI) research-all

report:
	$(CLI) report

paper-start:
	$(CLI) paper-start

demo-start:
	$(CLI) demo-start

live-start:
	$(CLI) live-start

status:
	$(CLI) status

pause:
	$(CLI) pause

resume:
	$(CLI) resume

kill:
	$(CLI) kill

test:
	pytest -q
