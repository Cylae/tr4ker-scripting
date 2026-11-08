PYTHON ?= python3
NPM ?= npm
NEXT_DIR := next/pimpmyshoutbox

.DEFAULT_GOAL := help

.PHONY: help doctor audit build check clean list bump release syntax test next-install next-test next-build verify

help: ## Show the available targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

audit: ## Print size/safety hotspots of the legacy userscripts
	$(PYTHON) tools/audit_userscripts.py

build: ## Build the legacy userscripts into dist/
	$(PYTHON) tools/build_userscripts.py

check: ## Validate metadata and JavaScript syntax (needs node)
	$(PYTHON) tools/build_userscripts.py --check
	$(PYTHON) tools/check_userscripts_syntax.py

syntax: ## Run node --check on every legacy userscript
	$(PYTHON) tools/check_userscripts_syntax.py

test: ## Run the Python tooling unit tests
	$(PYTHON) -m unittest discover tests

next-install: ## Install the PimpMyShoutbox Next dependencies (npm ci)
	cd $(NEXT_DIR) && $(NPM) ci

next-test: ## Run the PimpMyShoutbox Next test suite
	cd $(NEXT_DIR) && $(NPM) test

next-build: ## Build and syntax-check the PimpMyShoutbox Next bundle
	cd $(NEXT_DIR) && $(NPM) run check

verify: ## Run every gate that CI runs (with a pass/fail summary)
	$(PYTHON) tools/tr4ker.py verify

doctor: ## Check Python, Node, npm, git and the configuration
	$(PYTHON) tools/tr4ker.py doctor

clean: ## Remove generated build output
	rm -rf dist $(NEXT_DIR)/dist

list: ## List scripts with their version and install URLs
	$(PYTHON) tools/tr4ker.py list --urls

bump: ## Bump a version: make bump SCRIPT=<id> VERSION=<x.y.z>
ifndef SCRIPT
	$(error SCRIPT is required, for example: make bump SCRIPT=pimpmyshoutbox VERSION=3.0.33)
endif
ifndef VERSION
	$(error VERSION is required, for example: make bump SCRIPT=pimpmyshoutbox VERSION=3.0.33)
endif
	$(PYTHON) tools/bump_version.py $(SCRIPT) $(VERSION)

release: bump build ## Bump a version, then rebuild the legacy artifacts
