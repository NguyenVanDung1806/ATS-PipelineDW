# Edge Cases — Strategy Document

> These 11 edge cases are pre-loaded into `.claude/skills/edge-case-checklist/SKILL.md`.
> Claude auto-checks these whenever reviewing code.
> This file is the human-readable reference with full context.

---

## EC-01: Null / Missing API Fields

**Scenario:** Ad platform API returns `null` spend or missing field after an update.

**Impact:** NULL inserted into fact table → dashboard shows wrong numbers silently.

**Strategy:**
- Pydantic `Field(ge=0)` on all numeric fields — fail immediately on bad data
- `ConfigDict(extra="ignore")` — handle unknown fields gracefully
- Task fails loudly on `ValidationError` — never swallow exceptions
- Alert sent, data from previous day preserved in DW

---

## EC-02: API Rate Limits

**Scenario:** Facebook 200 calls/hour, TikTok 1000 calls/day — exceeded during pull.

**Impact:** Request fails mid-extraction → partial data in staging.

**Strategy:**
- `tenacity` retry with `wait_exponential(min=60, max=300)`
- `stop_after_attempt(3)` — don't retry forever
- Use batch API endpoints where available (FB Insights batch mode)
- Log retry attempts via `before_sleep_log`

---

## EC-03: CRM API Downtime

**Scenario:** Live1/CRM vendor API returns 503 during pipeline run.

**Impact:** `fact_leads` not updated → dashboard shows stale lead data.

**Strategy:**
- CRM extractor has independent retry from ad platform extractors
- If CRM fails after retries: skip CRM task, continue ad platform tasks
- Log failure to `meta.pipeline_runs` with full error
- Slack alert with severity HIGH
- Dashboard shows `last_updated` timestamp so team knows data is stale

---

## EC-04: Duplicate Leads (Ad Platform vs CRM)

**Scenario:** User submits both FB Lead Form AND website form → CRM deduplicates to 1 lead, FB reports 2.

**Impact:** CPL from Ads Manager ≠ CPL in DW → marketing team confused.

**Strategy:**
- CRM is source of truth for lead count (already deduped)
- Ad platform data is source of truth for spend/impressions/clicks only
- CPL in DW = `CRM spend / CRM leads` (not ad platform lead count)
- Dashboard always shows note: "CPL based on CRM leads (deduped)"

---

## EC-05: Leads Without UTM Attribution

**Scenario:** FB Lead Form submissions don't pass through website → no UTM captured.

**Impact:** `campaign_id = NULL` in `fact_leads` → can't calculate CPL per campaign.

**Strategy:**
- FB Lead Form leads: use `fb_lead_id` as join key to `fct_ad_spend`
- Website leads: use UTM params captured on landing page
- Organic/unattributed: `source_type = 'organic'`, tracked separately
- Dashboard shows `% unattributed` as a quality metric

---

## EC-06: Attribution Window (Retroactive Updates)

**Scenario:** Facebook attributes a conversion up to 7 days after click → data for day 10 gets updated on day 15, 16, 17.

**Impact:** If only pulling "today", historical data becomes stale and wrong.

**Strategy:**
- Always lookback 7 days in extractor: `get_date_range(lookback_days=7)`
- dbt incremental: `WHERE date >= MAX(date) - INTERVAL '7 days'`
- UPSERT (not INSERT) ensures historical rows get updated
- Dashboard note: "Numbers may differ from yesterday's screenshot — this is expected"

---

## EC-07: VPS Disk / Resource Exhaustion

**Scenario:** MinIO raw data accumulates, PostgreSQL WAL grows, disk hits 100%.

**Impact:** Pipeline fails, MinIO can't write, PostgreSQL may crash.

**Strategy:**
- Alert when disk > 80% (Airflow sensor checks daily)
- MinIO lifecycle: compress files after 30 days
- Staging tables TRUNCATE each run (no accumulation)
- Airflow pipelines staggered by 15 min to avoid concurrent resource spikes
- Estimated growth: ~200MB/year for typical DE project — manageable

---

## EC-08: API Schema Changes from Vendor

**Scenario:** CRM vendor renames `phone_number` → `phone` in API response. FB deprecates a field.

**Impact:** Pydantic validation fails → pipeline stops. Or worse: silently loads NULL.

**Strategy:**
- `ConfigDict(extra="ignore")` — new fields don't crash the pipeline
- Required fields fail loudly via Pydantic if removed
- Raw JSON in MinIO = original response, can reprocess with updated schema
- `on_schema_change='fail'` in dbt — explicit, not silent schema drift
- Process: detect → update Pydantic model → reprocess from MinIO → done

---

## EC-09: Data Not Finalized at Pipeline Run Time

**Scenario:** Pipeline runs at 6h ICT, but FB/Google don't finalize previous day's data until ~2h UTC (9h ICT).

**Impact:** Pull at 6h ICT gets incomplete data for yesterday → permanent undercount.

**Strategy:**
- Schedule all DAGs at 9h ICT (2h UTC): `schedule_interval = "0 2 * * *"`
- 7-day lookback ensures even slightly delayed data gets captured on next run
- Platform stagger: FB 9h, GG 9h15, TikTok 9h30, Zalo 9h45, CRM 10h

---

## EC-10: Campaign Targeting Multiple Offices

**Scenario:** Campaign "DuHocUc_2026" runs targeting both HCM and HN — no clear office tag.

**Impact:** Dashboard can't attribute spend to an office → `office = UNKNOWN`.

**Strategy (short term):**
- Enforce campaign naming convention: `[PLATFORM]_[MARKET]_[OFFICE]_[YEAR][Q]`
- dbt extracts office: `SPLIT_PART(campaign_name, '_', 3)`
- `CASE WHEN ... IN ('HCM','HN','DN') THEN ... ELSE 'UNKNOWN'` handles edge cases
- Track `% UNKNOWN` as a data quality metric

**Strategy (long term):**
- Separate ad sets per office within one campaign
- Map `ad_set → office` in `dim_campaign`

---

## EC-11: Counselor Office Transfer (SCD Type 2)

**Scenario:** Counselor A moves from HCM to HN mid-year → their historical HCM leads shouldn't be re-attributed.

**Impact:** If using current office, all historical performance shifts to HN.

**Strategy:**
- `dim_counselor` uses SCD Type 2: `valid_from`, `valid_to`, `is_current`
- On transfer: close old record (`valid_to = today`), create new record with new office
- `fact_leads` joins on counselor at time of lead creation, not current office
- Query pattern: `JOIN dim_counselor ON lead.counselor_id = dim.id AND lead.created_at BETWEEN dim.valid_from AND COALESCE(dim.valid_to, '9999-12-31')`
