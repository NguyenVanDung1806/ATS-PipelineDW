# ATS Marketing Data Pipeline — Project Brain

> Auto-loaded by Claude Code every session.
> Contains architectural decisions, rules, and context from Design Doc v1.0.
> DO NOT delete. Update "Current Phase" section daily.

---

## Project Identity
- **Project**: ATS (Avenue to Success) — Marketing Data Pipeline
- **Company**: Tư vấn du học, 3 văn phòng: HCM, HN, DN | 500–800 SV/năm | 30–60 nhân sự
- **Stack**: Airflow · MinIO · PostgreSQL · dbt Core · Metabase · Docker Compose on VPS
- **Started**: 2026-03-17
- **Design Doc**: `ATS_Marketing_Pipeline_Design_v1.0.docx`

## Data Sources
- [x] Facebook Ads (spend, impressions, clicks, leads + Lead Form API)
- [x] Google Ads (spend, impressions, clicks, conversions)
- [x] TikTok Ads (spend, impressions, clicks, leads)
- [x] Zalo Ads (spend, impressions, clicks, leads)
- [x] CRM: Live1 (leads, stages, counselors, contracts)
- [ ] Email/SMS/offline — out of scope Phase 1

## Stakeholders & Dashboards
| Person | Role | Dashboard |
|--------|------|-----------|
| General Director / Deputy GD | Executive | Executive Dashboard (monthly totals, CPA, office ranking) |
| Simon (Marketing Manager) | Marketing | Marketing Performance (CPL, platform comparison, budget pacing) |
| Counselling Manager | CRM Pipeline | Lead funnel, speed-to-lead, counselor conversion |

---

## Absolute Rules — Never Violate

1. **NO hardcoded secrets** — always `os.environ["KEY"]`, never literals
2. **NO direct INSERT to fact tables** — always UPSERT via dbt incremental
3. **ALWAYS Pydantic validate** API response before any staging load
4. **ALWAYS lookback 7 days** when pulling ad platform data (attribution window)
5. **ALWAYS upload to MinIO first**, then load to staging (raw = safety net)
6. **ALWAYS run `dbt test` after `dbt run`** — never skip, ever
7. **ALWAYS stagger pipeline schedules** — FB 9h, GG 9h15, TikTok 9h30, CRM 10h ICT
8. **Campaign names** must follow: `[PLATFORM]_[MARKET]_[OFFICE]_[YEAR][Q]_[OBJ]`
9. **CRM is source of truth for lead count** — not ad platform (CRM deduplicates)
10. **CPL formula**: CRM spend / CRM leads (not FB/GG leads count)
11. **Fail loudly** — pipeline fail must alert Slack immediately, never fail silently

---

## Architecture Decisions (decided — don't revisit)

| Decision | Choice | Reason |
|----------|--------|--------|
| Transform pattern | ELT (not ETL) | Logic in dbt, versioned SQL |
| Staging lifecycle | TRUNCATE each run | Idempotent, fresh every time |
| Raw data policy | Immutable in MinIO, never delete | Reprocess safety net |
| Fact table write | dbt incremental UPSERT | No duplicates, idempotent |
| Partitioning | pg_partman, monthly | Query performance + maintenance |
| Attribution window | 7-day lookback | FB/GG retroactive updates |
| Lead source of truth | CRM Live1 (not ad platform) | CRM deduplicates, ad platform doesn't |
| Schedule time | 9h ICT (2h UTC) staggered | Ad data finalized by then |
| Alerting | Slack webhook | On failure + data freshness |
| Currency | TBD (Open Question #3) | Need confirm USD vs VND vs both |
| Vendor independence | Business logic in dbt only | Can swap CRM/tool without losing history |

---

## PostgreSQL Schema Design

```
raw.*    → staging buffer, TRUNCATE before each pipeline run
dw.*     → warehouse (fact/dim, partitioned monthly, UPSERT only)
meta.*   → observability (pipeline_runs, data_quality_log, alert_log — append only)
```

### Fact Tables

**fct_ad_spend** — partition by month (date)
- Unique key: `(date, platform, campaign_id, ad_set_id, ad_id)`
- Columns: date, platform, campaign_id, ad_set_id, ad_id, office, spend, impressions, clicks, leads, updated_at

**fct_leads** — partition by month (created_at)
- Unique key: `lead_id`
- Columns: lead_id, created_at, platform_source, source_type, campaign_id, fb_lead_id, office, counselor_id, stage, is_duplicate, updated_at
- Stages: new → qualified → appointment → contract → lost

**fct_contracts** — Phase 4
- Columns: contract value, signed_at, office, counselor_id

### Dimension Tables
- **dim_campaign**: campaign metadata, office tag parsing
- **dim_office**: HCM | HN | DN
- **dim_counselor**: SCD Type 2 (valid_from, valid_to, is_current) — handles office transfers
- **dim_date**: standard date dimension

### Staging Tables
- raw.stg_fb_ads, raw.stg_google_ads, raw.stg_tiktok_ads, raw.stg_zalo_ads, raw.stg_crm_leads

---

## Data Flow

```
Ad Platforms / CRM API
  └─[Extract — Airflow, daily 9h ICT, lookback 7 days]
     └─[Pydantic validate]──► MinIO ats-datalake/raw/{platform}/{entity}/year=Y/month=M/day=D/
                                       │
                              [TRUNCATE staging]
                                       │
                              PostgreSQL raw.stg_{platform}
                                       │
                              [dbt run + dbt test]
                                       │
                              PostgreSQL dw.fct_{entity} + dw.dim_{entity}
                                       │
                              Metabase Dashboards (3 tiers)
```

---

## Edge Cases (from Design Doc Section 5)

| ID | Case | Strategy |
|----|------|----------|
| EC-01 | FB API null/missing fields | Pydantic `Field(ge=0)` — fail fast, don't load |
| EC-02 | FB rate limit (200/hr) | `tenacity` exponential backoff 60→120→240s, batch mode |
| EC-03 | CRM API down | Retry 3x, skip CRM task if fail, keep yesterday's data, alert HIGH |
| EC-04 | Duplicate leads FB vs CRM | CRM = source of truth for lead count, always |
| EC-05 | Leads without UTM | FB: use fb_lead_id join. Organic: bucket as 'Unattributed' |
| EC-06 | Attribution window conflict | 7-day lookback + UPSERT = always latest values |
| EC-07 | VPS disk full | Alert at 80%, MinIO compress after 30d, ~2GB for 5 years |
| EC-08 | Schema change from vendor | Pydantic alias support, reprocess from MinIO raw |
| EC-09 | Data not ready at pipeline time | Run 9h ICT (2h UTC), lookback covers gaps |
| EC-10 | 1 campaign multi-office | Enforce naming convention, separate ad sets per office |
| EC-11 | Counselor changes office | dim_counselor SCD Type 2 |

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
| Scaffold extractor | `/new-extractor [platform]` | Sonnet | Creates extract.py, schema.py, test |
| Phase planning | `/run-phase [0-4]` | Opus | Detailed execution plan per phase |
| Pre-merge check | `/validate-pipeline` | Sonnet | Security + dbt + infra checks |

---

## Naming Conventions

### dbt Models
```
stg_{source}_{entity}        staging/        stg_fb_ads, stg_crm_leads
int_{entity}_{action}        intermediate/   int_leads_reconciled, int_spend_enriched
fct_{entity}                 marts/          fct_ad_spend, fct_leads, fct_contracts
dim_{entity}                 dimensions/     dim_campaign, dim_office, dim_counselor
rpt_{metric}_{grain}         marts/          rpt_cpl_by_platform, rpt_office_summary
```

### Campaigns (mandatory for office attribution)
```
{PLATFORM}_{MARKET}_{OFFICE}_{YEAR}{Q}_{OBJECTIVE}
FB_DuHocUc_HCM_2026Q1_Lead
GG_DuHocMy_HN_2026Q2_Conv
TT_DuHocCanada_DN_2026Q1_View
ZL_DuHocNhat_HCM_2026Q2_Lead
```
Office tags: `HCM` | `HN` | `DN` — no alternatives

### MinIO Paths
```
Bucket: ats-datalake
raw/{platform}/{entity}/year={Y}/month={M}/day={D}/{platform}_{entity}_{YYYYMMDD}_{HHmmss}.json
processed/{platform}/{entity}/year={Y}/month={M}/
```

---

## Known Gotchas (update as discovered)

- FB Insights API: use `time_range` dict, NOT `date_preset` for custom ranges
- FB Lead Form: không có UTM → dùng `fb_lead_id` làm join key với campaign
- FB rate limit: 200 calls/hour — dùng batch mode (50 requests/batch)
- FB leads: ATS dùng 3 action types — `offsite_conversion.fb_pixel_lead` (priority) > `lead` > `onsite_web_lead` — KHÔNG cộng cả 2 (double-count)
- FB leads = 0 không có nghĩa là campaign không chạy — có thể là Traffic objective, check action_type trước
- FB currency ATS = VND (confirmed 2026-03-18, Open Question #3 resolved)
- FB ad account ID: extractor tự thêm prefix `act_` — không cần trong .env
- pg_partman: run `partman.run_maintenance()` after creating parent table
- dbt incremental UPSERT: must include partition key in `unique_key` list
- Airflow 2.9: use `@task` decorator pattern, avoid old `PythonOperator` where possible
- Pydantic v2: `class Config` → `model_config = ConfigDict(extra='ignore')`
- MinIO: bucket `ats-datalake` must exist before first upload (create in init script)
- TikTok API: rate limit resets at midnight UTC, not per-hour window
- CRM Live1: nếu API down → skip, giữ data cũ, alert HIGH (acceptable 1-day delay)
- Dashboard CPL: luôn chú thích "CPL tính theo CRM leads (đã dedup), có thể khác Ads Manager"

---

## Open Questions (from Design Doc Section 9)

| # | Question | Owner | Status |
|---|----------|-------|--------|
| 1 | CRM Live1 API auth: API key hay OAuth? Expire? | IT Lead + CRM Vendor | **Open** |
| 2 | Monthly budget per platform? (budget pacing) | Simon | **Open** |
| 3 | Track spend VND hay USD hay cả hai? | Simon + GD | **Open** |
| 4 | CRM stage definitions chuẩn hóa chưa? | Counselling Manager | **Open** |
| 5 | FB Lead Form sync tự động vào Live1? | IT Lead + CRM Vendor | **Open** |
| 6 | Dashboard cần role-based access? | GD | **Open** |

---

## Project Phases

| Phase | Name | Timeline | Status |
|-------|------|----------|--------|
| 0 | Infrastructure Setup | Tuần 1 | In Progress |
| 1 | Facebook Ads Pipeline | Tuần 2–3 | Not started |
| 2 | Multi-platform + CRM | Tuần 4–6 | Not started |
| 3 | Observability & Quality | Tuần 7–8 | Not started |
| 4 | CRM Pipeline Dashboard | Tuần 9–10 | Not started |

---

## Current Phase

```
Phase:       1 — Facebook Ads Pipeline
Status:      In Progress — extractor + DAG done, end-to-end pending Docker up
Last session: 2026-03-18
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
