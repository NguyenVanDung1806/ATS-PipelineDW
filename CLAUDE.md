# DE Senior Template — Project Brain

> This file is auto-loaded by Claude Code every session.
> It contains architectural decisions, rules, and context.
> DO NOT delete. Update the "Current Phase" section daily.

---

## Project Identity
- Template: DE Senior Template v1.0
- Maintainer: [YOUR NAME]
- Stack: Airflow · MinIO · PostgreSQL · dbt · Metabase
- Started: [DATE]

## Data Sources
> Customize this section for your project:
- [ ] Platform 1: [e.g., Facebook Ads]
- [ ] Platform 2: [e.g., Google Ads]
- [ ] CRM: [e.g., Live1, HubSpot, Salesforce]
- [ ] Other: [e.g., Website events, Internal DB]

---

## Absolute Rules — Never Violate

1. **NO hardcoded secrets** — always `os.environ["KEY"]`, never literals
2. **NO direct INSERT to fact tables** — always UPSERT via dbt incremental
3. **ALWAYS Pydantic validate** API response before any staging load
4. **ALWAYS lookback 7 days** when pulling ad platform data (attribution window)
5. **ALWAYS upload to MinIO first**, then load to staging (raw = safety net)
6. **ALWAYS run `dbt test` after `dbt run`** — never skip, ever
7. **ALWAYS stagger pipeline schedules** — avoid concurrent VPS resource spikes
8. **Campaign names** must follow: `[PLATFORM]_[MARKET]_[OFFICE]_[YEAR][Q]_[OBJ]`

---

## Architecture Decisions (decided — don't revisit)

| Decision | Choice | Reason |
|----------|--------|--------|
| Transform pattern | ELT (not ETL) | Logic in dbt, versioned SQL |
| Staging lifecycle | TRUNCATE each run | Idempotent, fresh every time |
| Raw data policy | Immutable, never delete | Reprocess safety net |
| Fact table write | dbt incremental UPSERT | No duplicates, idempotent |
| Partitioning | pg_partman, monthly | Query performance + maintenance |
| Attribution window | 7-day lookback | FB/GG retroactive updates |
| Lead source of truth | CRM (not ad platform) | CRM deduplicates, ad platform doesn't |
| Schedule time | 9h ICT (2h UTC) | Ad data finalized by then |
| Alerting | Slack webhook | On failure + data freshness |

---

## PostgreSQL Schema Design

```
raw.*    → staging buffer, TRUNCATE before each pipeline run
dw.*     → warehouse (fact/dim, partitioned monthly, UPSERT only)
meta.*   → observability (pipeline_runs, quality_log — append only)
```

---

## Data Flow

```
API Call
  └─[Pydantic validate]──► MinIO raw/{platform}/year=X/month=X/day=X/
                                    │
                           [TRUNCATE staging]
                                    │
                           PostgreSQL raw.stg_{platform}
                                    │
                           [dbt run + dbt test]
                                    │
                           PostgreSQL dw.fct_{entity}
                                    │
                           Metabase Dashboard
```

---

## Common Commands

```bash
# Infrastructure
docker-compose -f infra/docker-compose.yml up -d
docker-compose -f infra/docker-compose.yml ps
docker-compose -f infra/docker-compose.yml logs -f airflow-scheduler

# dbt
cd dbt
dbt debug                              # test connection
dbt run --select staging               # run staging only
dbt test --select staging              # test staging
dbt run --select marts                 # run fact tables
dbt run --select tag:daily             # run by tag

# Validation
python scripts/validate/check_pipeline.py   # full health check
python scripts/validate/check_credentials.py # security scan

# Airflow
airflow dags list
airflow dags trigger {dag_id}
airflow dags backfill -s 2026-03-01 -e 2026-03-17 {dag_id}
```

---

## Agent Usage Guide

| Task | Agent / Skill | Model | How to invoke |
|------|--------------|-------|---------------|
| Design new schema | `pipeline-architect` | Opus | "Use pipeline-architect agent to design..." |
| Write extractor | `pydantic-extractor` skill | Sonnet | Auto-loads when editing extractors/ |
| Write dbt model | `dbt-conventions` skill | Sonnet | Auto-loads when editing dbt/models/ |
| Write DAG | `airflow-dag-pattern` skill | Sonnet | Auto-loads when editing dags/ |
| Review code | `edge-case-checklist` skill | Sonnet | Auto-loads on review requests |
| Optimize SQL | `sql-optimizer` skill | Sonnet | Auto-loads on complex queries |
| Search codebase | `codebase-explorer` | Haiku | "Use codebase-explorer to find..." |
| Pre-merge scan | `security-auditor` | Sonnet | "Use security-auditor on changed files" |
| Debug mismatch | `reconciliation-analyst` | Opus | "Use reconciliation-analyst to investigate..." |
| Review dbt models | `dbt-reviewer` | Sonnet | "Use dbt-reviewer on this model" |

---

## Naming Conventions

### dbt Models
```
stg_{source}_{entity}        staging/
int_{entity}_{action}        intermediate/
fct_{entity}                 marts/
dim_{entity}                 dimensions/
rpt_{metric}_{grain}         marts/ (pre-aggregated for Metabase)
```

### Campaigns (mandatory for office attribution)
```
{PLATFORM}_{MARKET}_{OFFICE}_{YEAR}{Q}_{OBJECTIVE}
FB_DuHocUc_HCM_2026Q1_Lead
GG_DuHocMy_HN_2026Q2_Conv
TT_DuHocCanada_DN_2026Q1_View
```

### MinIO Paths
```
raw/{platform}/{entity}/year={Y}/month={M}/day={D}/{platform}_{date}_{time}.json
processed/{platform}/{entity}/year={Y}/month={M}/
```

---

## Known Gotchas (update as discovered)

- FB Insights API: use `time_range` dict, NOT `date_preset` for custom ranges
- pg_partman: run `partman.run_maintenance()` after creating parent table
- dbt incremental UPSERT: must include partition key in `unique_key` list
- Airflow 2.9: use `@task` decorator pattern, avoid old `PythonOperator` where possible
- Pydantic v2: `class Config` → `model_config = ConfigDict(extra='ignore')`
- MinIO: bucket must exist before first upload (create in init script)
- TikTok API: rate limit resets at midnight UTC, not per-hour window

---

## Current Phase

```
Phase:       0 — Infrastructure Setup
Status:      [ ] Not started
Last session: —
```

**Update this section every session.**

---

## Session Protocol

### Start of session
```
Read CLAUDE.md and MEMORY.md.
Current phase: [X]. Today's goal: [describe].
Before coding: tell me your plan.
```

### End of session
```
Update MEMORY.md:
- What was completed today
- Any new gotchas discovered
- Blocked items
- Next session's first task
```

### Before merging any branch
```
1. Use security-auditor agent on all changed files
2. Run: python scripts/validate/check_pipeline.py
3. Run: cd dbt && dbt test
4. Update MEMORY.md
```
