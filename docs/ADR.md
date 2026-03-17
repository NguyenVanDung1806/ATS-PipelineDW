# Architecture Decision Records (ADR)

> Record every significant architecture decision here.
> Format: Date · Decision · Context · Consequences

---

## ADR-001: ELT over ETL

**Date:** Template default
**Status:** Decided

**Decision:** Use ELT pattern — Extract and Load raw data first, Transform in dbt.

**Context:** Traditional ETL transforms in Python before loading. With dbt, SQL-based transformations are version-controlled, testable, and rerunnable from raw data.

**Consequences:**
- Raw data preserved in MinIO (reprocess anytime)
- All business logic lives in dbt (single source of truth for transformations)
- Python extractors are thin — only validate and load, no business logic

---

## ADR-002: PostgreSQL for both staging and DW

**Date:** Template default
**Status:** Decided

**Decision:** Use PostgreSQL with separate schemas (`raw`, `dw`, `meta`) instead of separate databases or a managed DW like BigQuery/Snowflake.

**Context:** At small-to-medium scale (<100M rows/year), PostgreSQL with pg_partman handles the workload well. Self-hosted = no vendor costs, no lock-in.

**Consequences:**
- Cost: ~$0 additional (same VPS)
- Limitation: not horizontally scalable; migrate to Snowflake/BigQuery when row counts exceed 500M+
- Benefit: SQL is portable — dbt models work on any SQL DB

---

## ADR-003: MinIO as raw data lake

**Date:** Template default
**Status:** Decided

**Decision:** Store all raw API responses as JSON in MinIO before any DB load.

**Context:** Protects against: API schema changes (EC-08), pipeline bugs (reprocess), auditing needs, vendor migration (raw data is always available regardless of CRM/platform changes).

**Consequences:**
- Raw data grows ~200MB/year for typical project — acceptable
- Any pipeline bug can be fixed and reprocessed from raw without re-calling APIs
- MinIO is S3-compatible — migrate to AWS S3 with zero code changes if needed

---

## ADR-004: CRM as source of truth for lead count

**Date:** Template default
**Status:** Decided

**Decision:** CRM lead count is used for CPL calculation, not ad platform lead count.

**Context:** Ad platforms count a "lead" when their form is submitted — no deduplication. CRM deduplicates by phone/email. 1 person submitting 2 forms = 2 leads in FB, 1 lead in CRM.

**Consequences:**
- CPL in dashboard will differ from Ads Manager — this is intentional and correct
- Dashboard must note: "CPL based on CRM leads (deduped)"
- Reconciliation dashboard shows sync rate between platforms

---

## ADR-005: 7-day lookback on all ad platform pulls

**Date:** Template default
**Status:** Decided

**Decision:** Every ad platform extraction pulls the last 7 days of data, not just today.

**Context:** Facebook, Google, TikTok retroactively update conversion attribution within a 7-day window (EC-06). Pulling only "today" results in permanently understated historical metrics.

**Consequences:**
- Each pipeline run re-processes 7 days of data
- UPSERT in dbt ensures no duplicates despite re-processing
- Slightly higher API usage — acceptable given rate limits

---

## ADR-006: Airflow schedule at 9h ICT (2h UTC)

**Date:** Template default
**Status:** Decided

**Decision:** All pipelines scheduled at 9h ICT (2h UTC), not 6h ICT.

**Context:** Major ad platforms finalize previous day's data between midnight and 2h UTC. Running at 6h ICT (23h UTC day before) captures incomplete data (EC-09).

**Consequences:**
- Teams get fresh data by 9:30-10h ICT each morning
- 7-day lookback covers any data that was delayed beyond 2h UTC

---

*Add new ADRs below as project-specific decisions are made.*
