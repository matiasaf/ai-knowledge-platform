API_DIR := services/api
WEB_DIR := apps/web

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show the available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install backend and frontend dependencies from the lockfiles
	cd $(API_DIR) && uv sync
	cd $(WEB_DIR) && npm ci

.PHONY: api
api: ## Run the API with reload on http://localhost:8000
	cd $(API_DIR) && uv run uvicorn ai_knowledge_platform.main:app --reload --port 8000

.PHONY: web
web: ## Run the web app on http://localhost:3000
	cd $(WEB_DIR) && npm run dev

.PHONY: check-api
check-api: ## Lint, format-check, type-check and test the API
	cd $(API_DIR) && uv run ruff check .
	cd $(API_DIR) && uv run ruff format --check .
	cd $(API_DIR) && uv run mypy
	cd $(API_DIR) && uv run pytest
	cd $(API_DIR) && uv run python -m ai_knowledge_platform.retrieval.evaluation

.PHONY: eval-retrieval
eval-retrieval: ## Run the fixed retrieval evaluation and enforce its thresholds
	cd $(API_DIR) && uv run python -m ai_knowledge_platform.retrieval.evaluation

.PHONY: check-web
check-web: ## Lint, type-check, test, build and audit the web app
	cd $(WEB_DIR) && npm run lint
	cd $(WEB_DIR) && npm run typecheck
	cd $(WEB_DIR) && npm run test
	cd $(WEB_DIR) && npm run build
	cd $(WEB_DIR) && npm audit --audit-level=high

.PHONY: check
check: check-api check-web ## Run every quality gate that CI runs

.PHONY: format
format: ## Apply formatting and safe lint fixes to both projects
	cd $(API_DIR) && uv run ruff check --fix .
	cd $(API_DIR) && uv run ruff format .
	cd $(WEB_DIR) && npm run format
