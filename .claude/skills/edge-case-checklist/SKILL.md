---
name: edge-case-checklist
description: Apply when reviewing, checking, or validating any extractor,
  dbt model, DAG, or pipeline code. Auto-invoked when: reviewing new code,
  writing tests, before commits, any mention of review/check/validate/
  edge case/test coverage/before merge/is this correct/anything missing/
  double check/potential bug/null handling/looks good/ready to merge.
  Also triggers on: before commit, ready to merge, double check,
  potential bug, handle error, null handling, looks good, is this right.
context: fork
agent: Explore
allowed-tools: Read, Grep, Glob
---

# Edge Case Review Checklist

## Files changed since last commit (review these):
!`git diff --name-only HEAD 2>/dev/null | grep -E "\.(py|sql|yml)$" || git status --short 2>/dev/null | awk '{print $2}' | grep -E "\.(py|sql|yml)$" || echo "No changed files detected"`

## Current dbt test status:
!`cd dbt && dbt test --quiet 2>&1 | grep -E "(PASS|FAIL|ERROR)" | tail -5 2>/dev/null || echo "dbt not available — check manually"`

---

Run for EVERY extractor and dbt model. Report PASS ✓ / FAIL ✗ / N/A.

## EC-01: Null / missing API fields
- [ ] Pydantic `Field(ge=0)` on all numeric fields?
- [ ] `model_config = ConfigDict(extra="ignore")`?
- [ ] Task fails immediately on ValidationError?

## EC-02: Rate limit handling
- [ ] `tenacity` `@retry` decorator present?
- [ ] `wait_exponential(min=60, max=300)`?
- [ ] `stop_after_attempt(3)`?

## EC-04: Duplicate leads
- [ ] CPL uses CRM lead count (not ad platform)?
- [ ] `fct_leads` has unique constraint on `lead_id`?

## EC-06: Attribution window
- [ ] Extractor lookback 7 days (not just today)?
- [ ] dbt incremental: `MAX(date) - INTERVAL '7 days'`?

## EC-08: API schema changes
- [ ] `extra="ignore"` on Pydantic?
- [ ] Raw JSON stored in MinIO?

## EC-09: Data not finalized
- [ ] DAG scheduled at 9h ICT (2h UTC)?

## EC-10: Campaign multi-office
- [ ] `SPLIT_PART(campaign_name, '_', 3)` extracts office?
- [ ] `CASE WHEN ... ELSE 'UNKNOWN'` handles edge cases?

## Security
- [ ] No hardcoded API keys or passwords?
- [ ] All secrets via `os.environ["KEY"]`?

## Report format
```
EC-01: PASS ✓ — Pydantic Field(ge=0) present
EC-02: FAIL ✗ — Missing tenacity at line 47
EC-06: N/A   — Not an extractor
Security: PASS ✓
```


# Edge Case Review Checklist

Run for EVERY extractor and dbt model before marking done.
Report each as PASS ✓ / FAIL ✗ / N/A.

---

## EC-01: Null / missing API fields
- [ ] Pydantic `Field(ge=0)` on all numeric fields (spend, impressions, clicks, leads)?
- [ ] `model_config = ConfigDict(extra="ignore")` on Pydantic model?
- [ ] Task fails immediately on `ValidationError` — no partial load?
- [ ] No silent `try/except` that swallows validation errors?

## EC-02: Rate limit handling
- [ ] `tenacity` `@retry` decorator present on API call functions?
- [ ] `wait_exponential(min=60, max=300)` configured?
- [ ] `stop_after_attempt(3)` set?
- [ ] Correct exception types in `retry_if_exception_type`?
- [ ] Retry logged with `before_sleep_log`?

## EC-03: CRM API downtime
- [ ] CRM extractor has independent retry (separate from ad platform)?
- [ ] Pipeline continues if CRM fails (ad platform data still loads)?
- [ ] Failure logged to `meta.pipeline_runs` with error message?
- [ ] Slack alert sent on CRM failure?

## EC-04: Duplicate leads (ad platform vs CRM)
- [ ] CPL calculated using CRM lead count (not ad platform count)?
- [ ] Dashboard note: "CPL = CRM-based (deduped)"?
- [ ] `fct_leads` has unique constraint on `lead_id`?

## EC-05: Leads without UTM / attribution
- [ ] `source_type` column distinguishes `fb_lead_form` vs `website_form` vs `organic`?
- [ ] Unattributed leads tracked as `platform_source = NULL`?
- [ ] `% unattributed` metric visible in dashboard?

## EC-06: Attribution window (ad platform retroactive updates)
- [ ] Extractor uses `get_date_range(lookback_days=7)` — not just today?
- [ ] dbt incremental: `where date >= max(date) - interval '7 days'`?
- [ ] UPSERT (not INSERT) so historical data gets updated?

## EC-07: VPS disk / resource
- [ ] MinIO `lifecycle_policy` configured (compress after 30d)?
- [ ] Staging tables have `TRUNCATE` (not append) to prevent bloat?
- [ ] Airflow pipelines staggered (not all at 9h exactly)?

## EC-08: API schema changes from vendor
- [ ] `extra="ignore"` on Pydantic (no crash when API adds fields)?
- [ ] Raw JSON stored in MinIO (can reprocess with new schema)?
- [ ] `on_schema_change='fail'` in dbt config (explicit, not silent)?

## EC-09: Data not finalized at pipeline run time
- [ ] DAG `schedule_interval = "0 2 * * *"` (9h ICT, not 6h)?
- [ ] 7-day lookback covers any delayed data?

## EC-10: Campaign targeting multiple offices
- [ ] `SPLIT_PART(campaign_name, '_', 3)` correctly extracts office?
- [ ] `CASE WHEN ... IN ('HCM','HN','DN') THEN ... ELSE 'UNKNOWN'` handles edge cases?
- [ ] `UNKNOWN` office is trackable in dashboard (not silently dropped)?

## EC-11: Counselor office transfer (SCD2)
- [ ] `dim_counselor` has `valid_from`, `valid_to`, `is_current` columns?
- [ ] Historical leads link to counselor's office at time of creation?

## Security
- [ ] No hardcoded API keys, tokens, passwords anywhere in file?
- [ ] All secrets via `os.environ["KEY"]`?
- [ ] No credentials in comments or docstrings?

---

## Report format

```
EC-01: PASS ✓ — Pydantic Field(ge=0) + ConfigDict(extra='ignore') present
EC-02: FAIL ✗ — Missing tenacity retry on call_api() at line 47
EC-03: N/A   — Not a CRM extractor
EC-06: PASS ✓ — lookback 7 days in get_date_range()
EC-08: PASS ✓ — extra='ignore' + raw JSON in MinIO
Security: PASS ✓ — no hardcoded credentials found
```

**Block task completion on any FAIL.**
