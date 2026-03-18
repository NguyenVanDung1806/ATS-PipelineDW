# Airflow DAG Layer Context

> Auto-loaded khi Claude Code làm việc trong dags/
> Supplement root CLAUDE.md, không replace

## DAG Status
| DAG | Platform | Schedule | Status |
|-----|----------|----------|--------|
| template_pipeline | — | — | TEMPLATE — copy this |
| facebook_pipeline | facebook | 0 2 * * * (09:00 ICT) | ✓ LIVE — 3x end-to-end verified, idempotent |

## Schedule Convention
```
facebook:  "0 2 * * *"   → 09:00 ICT
google:    "15 2 * * *"  → 09:15 ICT
tiktok:    "30 2 * * *"  → 09:30 ICT
zalo:      "45 2 * * *"  → 09:45 ICT
crm:       "0 3 * * *"   → 10:00 ICT
```

## Create New DAG
```bash
# Copy template, then replace PLATFORM variable
cp dags/template_pipeline.py dags/facebook_pipeline.py
# Edit: PLATFORM = "facebook", SCHEDULE = "0 2 * * *"
```

## DAG-specific Gotchas
<!-- Add as discovered -->
- Always set max_active_runs=1 (prevent concurrent runs)
- on_failure_callback is REQUIRED — never remove it
- BashOperator for dbt tasks (not PythonOperator)

## Current Focus
Working on: Phase 2 — next platform extractor (Google Ads or TikTok)
