SHELL := /bin/bash

.PHONY: help dev stop logs test-all build-python-packages publish-python-packages publish-python-packages-test update-release-manifest check-version-sync
.DEFAULT_GOAL := help

help: ## Show targets
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

dev: ## Start local stack
	@docker compose up -d --build

stop: ## Stop local stack
	@docker compose down

logs: ## Follow logs
	@docker compose logs -f

test-all: ## Run repo test script
	@./scripts/run-all-tests.sh

build-python-packages: ## Build all Python packages in ./packages using uv
	@./scripts/publish-python-packages.sh --build-only

publish-python-packages: ## Build and publish all Python packages to PyPI using uv
	@./scripts/publish-python-packages.sh --publish --index pypi

publish-python-packages-test: ## Build and publish all Python packages to TestPyPI using uv
	@./scripts/publish-python-packages.sh --publish --index testpypi

update-release-manifest: ## Regenerate manifest.yaml from component versions
	@./scripts/release/update-manifest.sh --config release/components.yaml --output manifest.yaml

check-version-sync: ## Validate component version sources and manifest consistency
	@./scripts/release/check-version-sync.sh --config release/components.yaml --manifest manifest.yaml
