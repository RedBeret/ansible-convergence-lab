SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help precheck backup deploy verify drift-check rollback inject-drift reset demo test

help:
	@printf '%s\n' \
	'Available targets:' \
	'  precheck     Run validation and health checks' \
	'  backup       Capture the current simulator config' \
	'  deploy       Apply the desired config with Ansible' \
	'  verify       Assert the desired end state and save last-known-good' \
	'  drift-check  Detect synthetic drift and fail if drift exists' \
	'  rollback     Restore the last-known-good backup' \
	'  inject-drift Introduce synthetic drift for training' \
	'  reset        Reset the simulator to blank state' \
	'  demo         Run the full <5 minute demo path' \
	'  test         Execute pytest integration tests'

precheck:
	labctl precheck

backup:
	labctl backup

deploy:
	labctl deploy

verify:
	labctl verify

drift-check:
	labctl drift-check

rollback:
	labctl rollback

inject-drift:
	labctl inject-drift

reset:
	labctl reset

demo:
	labctl demo

test:
	labctl test

