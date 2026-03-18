# Session Log

> Claude reads this at START of every session to restore context.
> Update at END of every session — the Stop hook will remind you.

---

## QUICK CONTEXT (Claude reads this first)
```
Phase:        2 — Multi-Platform
Current file:        MEMORY.md
Last action:        Modified facebook_pipeline.py, test_extract.py
Next action:        —
Blocked on:        FB_ACCESS_TOKEN (cần từ Facebook Business Manager)
Last session:        2026-03-18
```

---

## Completed Tasks

### Phase 0 — Infrastructure ✅ HOÀN THÀNH 2026-03-17
- [x] CLAUDE.md rewritten from Design Doc v1.0
- [x] .env filled with real values (FERNET_KEY phải quoted: `"key="`)
- [x] docker-compose.yml updated (MinIO, PG, Airflow, Metabase)
- [x] All Docker services healthy — PG port 5434 (conflict với local PG)
- [x] PostgreSQL schemas: raw, dw, meta, partman created
- [x] pg_partman 5.4.3 installed (custom Dockerfile.postgres dùng debian image)
- [x] MinIO bucket `ats-datalake` initialized (6 folders)
- [x] dbt debug passes (profiles.yml port 5434)
- [x] Airflow connections configured: postgres_ats, minio_ats, slack_default, fb_ads, crm_live1

### Phase 1 — Facebook Ads Pipeline
- [ ] FB Ads extractor (Pydantic validation, tenacity retry)
- [ ] Raw JSON → MinIO upload
- [ ] Load MinIO → staging.stg_fb_ads
- [ ] dbt model: stg_fb_ads → fct_ad_spend (UPSERT, tests pass)
- [ ] Airflow DAG: fb_pipeline (daily 9h ICT, on_failure Slack)
- [ ] Idempotency verified (3x run, stable row count)
- [ ] Metabase: CPL by campaign (first dashboard)

### Phase 2 — Multi-Platform + CRM
- [ ] Google Ads extractor + pipeline
- [ ] TikTok Ads extractor + pipeline
- [ ] Zalo Ads extractor + pipeline
- [ ] CRM Live1 extractor → fct_leads
- [ ] int_leads_reconciled (FB leads ↔ CRM leads join)
- [ ] Marketing Performance dashboard (CPL, platform comparison, spend pacing)

### Phase 3 — Observability & Quality
- [ ] meta.pipeline_runs logging
- [ ] Data freshness check (alert if >25h stale)
- [ ] dbt tests: reasonable values (spend>0, leads>=0, CPL<threshold)
- [ ] Slack alerts: pipeline failure + data quality failure
- [ ] Executive dashboard + Office comparison

### Phase 4 — CRM Pipeline Dashboard
- [ ] fct_contracts (contract value, signed_at, office)
- [ ] Speed-to-lead metric
- [ ] Counselor performance (conversion by counselor by office)
- [ ] CRM Pipeline dashboard

---

## In Progress
- Phase 1: Facebook Ads Pipeline — chưa bắt đầu

## Blocked
- 6 Open Questions pending stakeholder answers (see CLAUDE.md Open Questions table)

## Discovered Gotchas
```
2026-03-17 Design: FB Lead Form không có UTM → dùng fb_lead_id join với campaign
2026-03-17 Design: dim_counselor cần SCD Type 2 vì counselor có thể chuyển office
2026-03-17 Design: Dashboard CPL phải chú thích "tính theo CRM leads, khác Ads Manager"
2026-03-17 Infra: PG port đổi sang 5434 (5432 bị local PG chiếm, 5433 cũng bị chiếm)
2026-03-17 Infra: AIRFLOW_FERNET_KEY phải quoted trong .env: "key=" (docker-compose strip dấu = cuối)
2026-03-17 Infra: postgres:16-alpine không có pg_partman → dùng Dockerfile.postgres (debian) + apt install
2026-03-17 Infra: Airflow 2.9.3 + flask-session 0.5.0 bug → fix bằng SESSION_BACKEND=securecookie
2026-03-17 Infra: init_schemas.sql phải tạo schema partman trước khi CREATE EXTENSION pg_partman
```

## Session Notes

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 20 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 19 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 18 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 18 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 18 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 17 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 13 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 13 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 12 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 12 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 9 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 7 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 7 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 7 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 2 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 2 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 2 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 2 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 2 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 2 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 2 files

### 2026-03-18 — Auto-logged
- Branch: main | Changed: 2 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 1 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 15 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 15 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 15 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 15 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 15 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 14 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 14 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 12 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 12 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 12 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 12 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 11 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 10 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 9 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 9 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 9 files

### 2026-03-17 — Auto-logged
- Branch: main | Changed: 4 files

### 2026-03-17 — Session 1 (Planning)
- Read Design Doc v1.0 fully
- Rewrote CLAUDE.md with all ATS-specific context
- Updated MEMORY.md with project details
- Next: /run-phase 0 execution plan
