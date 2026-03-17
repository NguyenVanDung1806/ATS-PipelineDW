# Conventions — DE Senior Template

## Campaign Naming (mandatory for office attribution)

```
[PLATFORM]_[MARKET]_[OFFICE]_[YEAR][Q]_[OBJECTIVE]

Examples:
  FB_DuHocUc_HCM_2026Q1_Lead
  GG_DuHocMy_HN_2026Q2_Conv
  TT_DuHocCanada_DN_2026Q1_View
  ZL_DuHocNZ_HCM_2026Q2_Message

PLATFORM : FB | GG | TT | ZL
OFFICE   : HCM | HN | DN  (no other values)
QUARTER  : Q1 | Q2 | Q3 | Q4
OBJECTIVE: Lead | Conv | View | Message | Traffic
```

## dbt Model Naming

```
stg_{source}_{entity}     → models/staging/
int_{entity}_{verb}       → models/intermediate/
fct_{entity}              → models/marts/
dim_{entity}              → models/dimensions/
rpt_{metric}_{grain}      → models/marts/

Examples:
  stg_facebook_ads
  stg_crm_leads
  int_leads_reconciled
  int_spend_enriched
  fct_ad_spend
  fct_leads
  fct_contracts
  dim_campaign
  dim_office
  dim_counselor
  rpt_cpl_daily
  rpt_office_monthly
```

## Python Files

```
extractors/{platform}/extract.py    → extractor class
extractors/{platform}/schema.py     → Pydantic models
extractors/{platform}/__init__.py   → empty
dags/{platform}_pipeline.py        → Airflow DAG
scripts/validate/check_*.py        → validation scripts
scripts/setup/init_*.py            → one-time setup
tests/unit/test_{module}.py        → unit tests
tests/integration/test_{flow}.py   → integration tests
```

## MinIO Path Structure

```
raw/{platform}/{entity}/year={Y}/month={M:02d}/day={D:02d}/{platform}_{date}_{time}.json

Examples:
  raw/facebook/ads/year=2026/month=03/day=17/facebook_2026-03-17_090032.json
  raw/crm/leads/year=2026/month=03/day=17/crm_2026-03-17_100015.json
  processed/facebook/ads/year=2026/month=03/  ← after dbt
```

## Environment Variables

```
# Format: {SERVICE}_{ATTRIBUTE}
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET
AIRFLOW_FERNET_KEY, AIRFLOW_SECRET_KEY
SLACK_WEBHOOK_URL
FACEBOOK_ACCESS_TOKEN, FACEBOOK_AD_ACCOUNT_ID
GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CUSTOMER_ID
CRM_API_BASE_URL, CRM_API_TOKEN
```

## Git Branches

```
main              → production-ready only
develop           → integration branch
feature/{task}    → new features
fix/{issue}       → bug fixes
phase/{n}         → phase-level work

Examples:
  feature/facebook-extractor
  feature/fct-ad-spend-model
  fix/cpl-null-division
  phase/1-facebook-pipeline
```

## Commit Messages (Conventional Commits)

```
feat: add Facebook ads extractor with Pydantic validation
fix: handle null spend in stg_facebook_ads
chore: scaffold dbt project structure
test: add EC-01 validation tests for FB extractor
docs: add edge case EC-06 attribution window strategy
refactor: extract MinIO upload to base class
perf: add index on fct_ad_spend(date, platform)
```
