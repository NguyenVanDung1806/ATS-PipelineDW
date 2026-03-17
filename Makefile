.PHONY: help setup up down logs ps dbt-run dbt-test dbt-all validate security clean

# ── Colors ────────────────────────────────────────────────────────────────────
CYAN  := \033[36m
GREEN := \033[32m
RESET := \033[0m
BOLD  := \033[1m

help: ## Show this help
	@echo ""
	@echo "$(BOLD)DE Senior Template — Commands$(RESET)"
	@echo "$(CYAN)══════════════════════════════════════$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────
setup: ## One-command first-time setup
	@echo "$(BOLD)Running setup...$(RESET)"
	@cp -n .env.example .env 2>/dev/null && echo "  Created .env from example" || echo "  .env already exists"
	python3 scripts/setup/init_all.py

# ── Infrastructure ────────────────────────────────────────────────────────────
up: ## Start all Docker services
	docker-compose -f infra/docker-compose.yml up -d
	@echo "$(GREEN)Services starting...$(RESET)"
	@echo "  Airflow:  http://localhost:8080"
	@echo "  MinIO:    http://localhost:9001"
	@echo "  Metabase: http://localhost:3000"

down: ## Stop all Docker services
	docker-compose -f infra/docker-compose.yml down

restart: ## Restart all services
	docker-compose -f infra/docker-compose.yml restart

ps: ## Show service status
	docker-compose -f infra/docker-compose.yml ps

logs: ## Follow all service logs
	docker-compose -f infra/docker-compose.yml logs -f

logs-airflow: ## Follow Airflow scheduler logs
	docker-compose -f infra/docker-compose.yml logs -f airflow-scheduler

logs-postgres: ## Follow PostgreSQL logs
	docker-compose -f infra/docker-compose.yml logs -f postgres

# ── dbt ───────────────────────────────────────────────────────────────────────
dbt-deps: ## Install dbt packages
	cd dbt && dbt deps

dbt-debug: ## Test dbt connection
	cd dbt && dbt debug

dbt-staging: ## Run + test staging models
	cd dbt && dbt run --select staging && dbt test --select staging

dbt-marts: ## Run + test mart models
	cd dbt && dbt run --select marts && dbt test --select marts

dbt-all: ## Run + test all models
	cd dbt && dbt run && dbt test
	@echo "$(GREEN)All dbt models passed$(RESET)"

dbt-docs: ## Generate and serve dbt docs
	cd dbt && dbt docs generate && dbt docs serve

# ── Validation ────────────────────────────────────────────────────────────────
validate: ## Full pipeline validation (run before every merge)
	python3 scripts/validate/check_pipeline.py

security: ## Scan for hardcoded credentials
	python3 scripts/validate/check_credentials.py

# ── Testing ───────────────────────────────────────────────────────────────────
test: ## Run all Python unit tests
	python3 -m pytest tests/ -v

test-extractors: ## Run extractor tests only
	python3 -m pytest tests/unit/ -v -k "extractor"

skill-test: ## Test skill trigger rates (should all be ≥85%)
	python3 scripts/skill-testing/test_triggers.py

skill-test-fix: ## Test triggers + show fix suggestions
	python3 scripts/skill-testing/test_triggers.py --fix

skill-tune: ## Auto-patch skill descriptions to improve trigger rate
	python3 scripts/skill-testing/test_triggers.py
	python3 scripts/skill-testing/tune_descriptions.py --apply
	python3 scripts/skill-testing/test_triggers.py

# ── Claude Code ───────────────────────────────────────────────────────────────
claude-plan: ## Open Claude Code with Opus for planning
	claude --model opus

claude: ## Open Claude Code with Sonnet (default)
	claude --model sonnet

claude-search: ## Open Claude Code with Haiku for quick search
	claude --model haiku

# ── Maintenance ───────────────────────────────────────────────────────────────
clean-staging: ## TRUNCATE all staging tables (use with caution)
	@echo "$(BOLD)This will TRUNCATE all raw.* tables. Continue? [y/N]$(RESET)" && read ans && [ $${ans:-N} = y ]
	psql $$DATABASE_URL -c "DO \$\$ DECLARE r RECORD; BEGIN FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='raw' LOOP EXECUTE 'TRUNCATE TABLE raw.' || r.tablename; END LOOP; END \$\$;"

check-disk: ## Check VPS disk usage
	df -h /
	@echo ""
	du -sh infra/minio_data 2>/dev/null || echo "MinIO data: check Docker volume"

env-check: ## Verify .env has all required variables
	@python3 -c "
import sys
required = ['POSTGRES_DB','POSTGRES_USER','POSTGRES_PASSWORD','MINIO_ACCESS_KEY','MINIO_SECRET_KEY','AIRFLOW_FERNET_KEY','SLACK_WEBHOOK_URL']
content = open('.env').read() if __import__('os').path.exists('.env') else ''
missing = [k for k in required if k not in content or k+'=CHANGE_ME' in content]
print('Missing/unfilled:', missing) if missing else print('All required env vars set')
sys.exit(1 if missing else 0)
"
