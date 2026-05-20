# ATS Marketing Data Platform Conversion Architecture

## 1. Purpose

This document defines how ATS should evolve from the current Facebook-only reporting pipeline into a scalable marketing data platform.

The current system can answer:

- How much did Facebook spend?
- How many platform leads did Facebook report?
- Which campaign/ad set performed better?

The next system must answer:

- How many leads did each platform generate?
- How many leads actually entered ATS CRM/Airtable?
- Which leads were valid, qualified, or invalid after telesales?
- Which campaigns created real business value?
- Why do Facebook, Agency, and ATS CRM numbers differ?
- Which rows are unmapped, duplicated, late, or unreliable?

The goal is not only to fix lead discrepancy. The goal is to build a production-grade marketing warehouse that can scale to:

- Facebook Ads
- Google Ads
- TikTok Ads
- Zalo Ads
- Airtable CRM
- Agency reports

---

## 2. Current Architecture

```text
Facebook Ads API
    |
    v
Airflow DAG: facebook_pipeline
    |
    v
MinIO raw JSON backup
    |
    v
raw.facebook_ads
    |
    v
dbt: stg_facebook_ads
    |
    v
dbt: dw.fct_ad_spend
    |
    v
Metabase Dashboard
```

Current strengths:

- Working Airflow orchestration.
- Backfill DAG exists.
- dbt models exist.
- CI/CD exists.
- Metabase is connected.
- Facebook spend/impressions/clicks/leads are already visible.

Current limitations:

- Facebook `actions` are requested but not stored in Postgres.
- `leads` is compressed into one ambiguous metric.
- `website_leads` and `on_facebook_leads` are not separated.
- `link_clicks` and `reach` are missing from the warehouse.
- Fact table is aggregated at `date + campaign + ad_set`, not ad-level.
- Airtable CRM leads are not integrated.
- Agency reports are not modeled.
- Campaign/ad names are not reliable keys.
- No canonical mapping layer exists.
- No reconciliation mart exists.

---

## 3. Target Architecture

```text
              +-------------------+
              | Facebook Ads API  |
              +-------------------+
                       |
              +-------------------+
              | Google Ads API    |
              +-------------------+
                       |
              +-------------------+
              | TikTok Ads API    |
              +-------------------+
                       |
              +-------------------+
              | Zalo Ads API      |
              +-------------------+
                       |
                       v
+--------------------------------------------------+
| Raw Layer                                         |
| raw.facebook_ads                                  |
| raw.google_ads                                    |
| raw.tiktok_ads                                    |
| raw.zalo_ads                                      |
| raw.airtable_leads                                |
| raw.agency_facebook_report                        |
+--------------------------------------------------+
                       |
                       v
+--------------------------------------------------+
| Staging Layer                                     |
| stg_facebook_ads                                  |
| stg_google_ads                                    |
| stg_tiktok_ads                                    |
| stg_zalo_ads                                      |
| stg_airtable_leads                                |
| stg_agency_facebook_report                        |
+--------------------------------------------------+
                       |
                       v
+--------------------------------------------------+
| Identity and Mapping Layer                        |
| map_marketing_entity_identity                     |
| dim_campaign                                      |
| dim_ad_set                                        |
| dim_ad                                            |
| dim_office                                        |
| dim_platform                                      |
+--------------------------------------------------+
                       |
                       v
+--------------------------------------------------+
| Normalized / Intermediate Layer                   |
| int_paid_ads_normalized                           |
| int_crm_leads_normalized                          |
| int_agency_report_normalized                      |
+--------------------------------------------------+
                       |
                       v
+--------------------------------------------------+
| Mart Layer                                        |
| fct_paid_ads_daily                                |
| fct_crm_leads_current                             |
| fct_marketing_performance_daily                   |
| fct_lead_reconciliation_daily                     |
+--------------------------------------------------+
                       |
                       v
+--------------------------------------------------+
| Metabase                                          |
| Executive Dashboard                               |
| Marketing Performance Dashboard                   |
| Lead Quality Dashboard                            |
| Reconciliation / Debug Dashboard                  |
| Data Quality Dashboard                            |
+--------------------------------------------------+
```

---

## 4. Core Design Principles

### 4.1 Do Not Use Campaign Name As A Key

Campaign names can differ across systems:

- Facebook Ads Manager may have the original campaign name.
- Agency report may use a display/export name.
- Airtable may contain a formatted business-friendly name.

Therefore:

- Keep raw names from every source.
- Create canonical campaign/ad set/ad keys.
- Use mapping status before joining data.
- Do not silently join unmatched records.

### 4.2 Keep Raw Payloads For Audit

Raw payloads are critical for reconciliation.

For Facebook, keep:

- `actions_json`
- `reach`
- `link_clicks`
- `website_leads`
- `on_facebook_leads`
- `platform_leads`

The current single `leads` column is not enough.

### 4.3 Separate Platform Metrics From Business Metrics

Platform metrics:

- Facebook leads
- Google conversions
- TikTok conversions
- Zalo leads

Business metrics:

- CRM leads
- valid leads
- qualified leads
- event confirmations
- event attendance
- applications
- enrollments

Dashboard decisions should eventually rely on business metrics, not only platform metrics.

### 4.4 Store Current State First, History Later

Airtable has UI logs, but history extraction may be harder.

V1 should build:

- `fct_crm_leads_current`

V2 can add:

- `fct_crm_lead_status_history`
- Airtable snapshots

### 4.5 Make Data Quality Visible

Bad data must not disappear.

The platform should expose:

- unmapped campaigns
- duplicate leads
- invalid leads
- wrong numbers
- platform vs agency discrepancy
- platform vs CRM discrepancy
- stale data
- failed extraction

---

## 5. Metric Dictionary V1

| Metric | Definition | Source | Usage |
| --- | --- | --- | --- |
| `platform_leads` | Leads/conversions reported by ad platform | Facebook/Google/TikTok/Zalo | Platform performance |
| `website_leads` | Website or pixel leads | Facebook actions / platform conversions | Reconcile website leads |
| `native_form_leads` | Native lead form submissions | Facebook lead form / platform native forms | Reconcile on-platform leads |
| `crm_leads` | Lead records in Airtable | Airtable | ATS operational truth |
| `valid_leads` | CRM leads with valid business status | Airtable Quality | Business quality |
| `qualified_leads` | Leads worth counselor follow-up | Airtable Quality / rating | Funnel quality |
| `event_confirmed_leads` | Leads confirming event attendance | Airtable | Event forecast |
| `event_attended_leads` | Leads that checked in at event | Airtable `Attend Event` | Event outcome |
| `lead_submissions` | Total submitted CRM records | Airtable | Volume |
| `unique_people` | Deduplicated people by phone/email | Airtable | Unique reach |
| `duplicate_leads` | Repeated leads by phone/email/campaign/event rule | Airtable | Data quality |
| `cpl_platform` | spend / platform_leads | Ads + platform leads | Platform CPL |
| `cpl_crm` | spend / crm_leads | Ads + Airtable | CRM CPL |
| `cpl_valid` | spend / valid_leads | Ads + Airtable Quality | Business CPL |

Quality mapping V1:

| Airtable Quality | valid_lead | qualified_lead | Notes |
| --- | --- | --- | --- |
| `Valid` | true | true | Strong lead |
| `Valid but No` | true | false | Valid person, weak/negative intent |
| `Keep following` | true | false | Interested but not ideal market/timing |
| `Invalid` | false | false | Keep in data, exclude from valid lead count |
| `Wrong number` | false | false | Keep in data, exclude from valid lead count |

Important:

- `Invalid` and `Wrong number` are not deleted.
- They remain in total submissions and CPL CRM submission.
- They are excluded from `valid_leads`.

---

## 6. Proposed Data Models

### 6.1 `raw.facebook_ads`

Purpose: store Facebook insights close to source.

Additive fields needed:

```text
account_id
campaign_id
campaign_name
ad_set_id
ad_set_name
ad_id
ad_name
date
spend
impressions
reach
clicks
link_clicks
actions_json
website_leads
native_form_leads
platform_leads
loaded_at
```

Do not remove existing fields yet. Use additive migration to avoid breaking production.

### 6.2 `stg_facebook_ads`

Purpose: clean and cast Facebook raw fields.

Rules:

- Rename only.
- Cast only.
- No business joins.
- No canonical mapping.
- Keep platform-specific metrics.

### 6.3 `raw.airtable_leads`

Purpose: store Airtable CRM records.

Expected fields:

```text
record_id
campaign
attend_event
family_name
given_name
phone
email
counselors
moved_to_counselor_report
note_by_telesales
last_update_l
ad_name
ad_set_name
ads_platform
counselors_follow_up_note
source_of_leads
office_location
time_to_study_abroad
role
quality
checked_phone_no_already
tracking_date
rating_by_counselors
event_location
confirmation_to_attend_event
raw_payload_json
loaded_at
```

### 6.4 `stg_airtable_leads`

Purpose: clean CRM data.

Rules:

- Standardize column names.
- Parse dates.
- Normalize quality values.
- Hash phone/email for deduplication.
- Keep PII carefully.
- Preserve raw campaign/ad names.

### 6.5 `map_marketing_entity_identity`

Purpose: map raw source names to canonical business identities.

```text
entity_type
source_system
source_platform
source_account_id
source_campaign_id
source_ad_set_id
source_ad_id
source_campaign_name
source_ad_set_name
source_ad_name
normalized_source_name
canonical_campaign_key
canonical_campaign_name
canonical_ad_set_key
canonical_ad_set_name
canonical_ad_key
canonical_ad_name
mapping_status
mapping_confidence
mapped_by
mapped_at
notes
```

Allowed `mapping_status`:

```text
suggested
approved
rejected
unmapped
```

Production rule:

- Dashboard marts should only use approved mappings for canonical reporting.
- Unmapped rows must appear in data quality dashboards.

### 6.6 `fct_paid_ads_daily`

Purpose: normalized paid ads performance across platforms.

Grain:

```text
date + platform + account_id + campaign_id + ad_set_id + ad_id
```

Fields:

```text
date
platform
account_id
campaign_id
campaign_name
ad_set_id
ad_set_name
ad_id
ad_name
canonical_campaign_key
canonical_ad_set_key
canonical_ad_key
mapping_status
spend
impressions
reach
clicks
link_clicks
website_leads
native_form_leads
platform_leads
updated_at
```

### 6.7 `fct_crm_leads_current`

Purpose: current CRM lead state.

Grain:

```text
record_id
```

Fields:

```text
record_id
tracking_date
last_update_at
lead_identity_key
phone_hash
email_hash
campaign_raw_name
ad_set_raw_name
ad_raw_name
ads_platform
canonical_campaign_key
canonical_ad_set_key
canonical_ad_key
mapping_status
quality
rating_by_counselors
is_valid_lead
is_qualified_lead
is_wrong_number
is_invalid
is_keep_following
is_valid_but_no
is_duplicate_person
is_duplicate_campaign
attend_event
confirmation_to_attend_event
moved_to_counselor_report
counselor
office_location
event_location
loaded_at
```

### 6.8 `fct_marketing_performance_daily`

Purpose: main dashboard fact.

Suggested grain:

```text
date + platform + canonical_campaign_key + office
```

Metrics:

```text
spend
impressions
reach
clicks
link_clicks
platform_leads
crm_leads
lead_submissions
unique_people
valid_leads
qualified_leads
event_confirmed_leads
event_attended_leads
duplicate_leads
cpl_platform
cpl_crm
cpl_valid
lead_to_valid_rate
lead_to_event_attend_rate
```

### 6.9 `fct_lead_reconciliation_daily`

Purpose: debug discrepancies between platform, agency, and CRM.

Suggested grain:

```text
date + platform + canonical_campaign_key + canonical_ad_set_key + canonical_ad_key
```

Fields:

```text
date
platform
campaign_name
ad_set_name
ad_name
canonical_campaign_key
mapping_status
platform_leads
agency_website_leads
agency_native_form_leads
agency_total_leads
crm_leads
valid_leads
platform_vs_agency_diff
platform_vs_crm_diff
agency_vs_crm_diff
reconciliation_status
updated_at
```

Allowed `reconciliation_status`:

```text
MATCH
PLATFORM_HIGHER_THAN_AGENCY
AGENCY_HIGHER_THAN_PLATFORM
PLATFORM_HIGHER_THAN_CRM
CRM_HIGHER_THAN_PLATFORM
MISSING_AGENCY_REPORT
MISSING_CRM_MAPPING
MISSING_PLATFORM_MAPPING
UNMAPPED
```

---

## 7. What To Do First

### Phase 1: Protect The Current System

Goal: avoid breaking the existing Facebook dashboard.

Tasks:

1. Keep `dw.fct_ad_spend` running.
2. Do not rename or remove existing columns yet.
3. Add new fields using additive migrations only.
4. Keep existing Metabase dashboard alive.

Reason:

The current dashboard is already useful. Architecture conversion should be incremental.

### Phase 2: Upgrade Facebook Raw Observability

Goal: make Facebook data auditable.

Tasks:

1. Add Facebook fields:
   - `reach`
   - `inline_link_clicks`
   - `actions`
2. Store `actions_json` in Postgres.
3. Parse:
   - `website_leads`
   - `native_form_leads`
   - `platform_leads`
4. Add retry handling for Facebook error code `4` and transient responses.
5. Backfill the audit window after deployment.

Why this comes first:

Current lead discrepancy cannot be debugged properly without raw action details.

### Phase 3: Create New Ad-Level Fact

Goal: stop relying on the old ad-set-level fact for audit.

Tasks:

1. Create `fct_paid_ads_daily`.
2. Use ad-level grain:
   - `date`
   - `platform`
   - `account_id`
   - `campaign_id`
   - `ad_set_id`
   - `ad_id`
3. Keep platform-specific lead metrics.
4. Add dbt uniqueness tests.
5. Add non-negative metric tests.

Why this comes before CRM join:

Agency reports include `Ad name`. Reconciliation needs ad-level data.

### Phase 4: Build Airtable CRM Extractor

Goal: bring ATS operational truth into the warehouse.

Tasks:

1. Create `raw.airtable_leads`.
2. Extract Airtable record ID.
3. Store all fields from lead retainer.
4. Store raw payload JSON.
5. Create `stg_airtable_leads`.
6. Create `fct_crm_leads_current`.
7. Hash phone/email.
8. Add duplicate flags.
9. Add quality flags.

Why this comes after ad-level fact:

CRM attribution depends on campaign/ad/ad set matching. We need ads entities ready first.

### Phase 5: Build Mapping Layer

Goal: prevent wrong joins caused by formatted names.

Tasks:

1. Create `map_marketing_entity_identity`.
2. Add normalized name logic.
3. Generate suggested mappings.
4. Require manual approval for uncertain mappings.
5. Flag unmapped rows.
6. Build unmapped data quality dashboard.

Why this is critical:

Airtable does not store platform IDs. Names are formatted. Joining directly by name is unsafe.

### Phase 6: Build Reconciliation Mart

Goal: explain differences between Facebook, Agency, and ATS.

Tasks:

1. Create `raw.agency_facebook_report` or dbt seed for agency files.
2. Create `stg_agency_facebook_report`.
3. Create `fct_lead_reconciliation_daily`.
4. Compare:
   - platform leads
   - agency website leads
   - agency on-Facebook leads
   - CRM leads
   - valid leads
5. Add status labels and discrepancy thresholds.

Why this matters:

This is the table used when numbers differ.

### Phase 7: Build Marketing Performance Mart

Goal: create the main executive/business reporting layer.

Tasks:

1. Create `fct_marketing_performance_daily`.
2. Join ads and CRM only after mapping is approved.
3. Add CPL metrics:
   - `cpl_platform`
   - `cpl_crm`
   - `cpl_valid`
4. Add funnel rates.
5. Build Metabase dashboard from this mart.

### Phase 8: Add More Platforms

Goal: scale beyond Facebook.

Suggested order:

1. Google Ads
2. TikTok Ads
3. Zalo Ads

For each platform:

1. Create raw table.
2. Create staging model.
3. Map native metrics to normalized fields.
4. Add to `int_paid_ads_normalized`.
5. Add to `fct_paid_ads_daily`.
6. Add reconciliation if agency reports exist.

---

## 8. Immediate Implementation Checklist

### Must Do Now

- [ ] Add Facebook `actions_json` storage.
- [ ] Add Facebook `reach`.
- [ ] Add Facebook `link_clicks`.
- [ ] Split `leads` into:
  - `website_leads`
  - `native_form_leads`
  - `platform_leads`
- [ ] Create new ad-level `fct_paid_ads_daily`.
- [ ] Keep old `fct_ad_spend` for compatibility.
- [ ] Design `raw.airtable_leads`.
- [ ] Design `fct_crm_leads_current`.
- [ ] Create mapping table design.

### Should Do Next

- [ ] Build Airtable extractor.
- [ ] Add phone/email hashing.
- [ ] Add duplicate lead logic.
- [ ] Add quality mapping logic.
- [ ] Import agency report as controlled source.
- [ ] Create reconciliation mart.
- [ ] Create data quality dashboard.

### Later

- [ ] Add CRM lead history/snapshot.
- [ ] Add Google Ads.
- [ ] Add TikTok Ads.
- [ ] Add Zalo Ads.
- [ ] Add alerting.
- [ ] Add role-based dashboard access.

---

## 9. Key Production Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Campaign names differ across systems | Wrong joins, wrong CPL | Canonical mapping layer |
| Facebook attribution updates late | Historical numbers change | Rolling reprocess window |
| Airtable lead updates overwrite state | Lost history | Current model first, snapshots later |
| Duplicate leads | Inflated performance | phone/email identity keys |
| Invalid leads mixed with valid leads | Misleading CPL | Separate total CRM leads vs valid leads |
| API rate limits | Failed backfills | Chunked backfill and retry/backoff |
| Token expiration | Pipeline failure | Secret management and credential checks |
| PII exposure | Compliance/security risk | Hash/mask phone and email |
| Agency exports inconsistent settings | Reconciliation disputes | Agency data contract |
| Unmapped rows hidden | Silent wrong data | Unmapped dashboard and tests |

---

## 10. Open Questions Before Production V1

These do not block the first engineering step, but they should be answered before declaring the platform production-ready:

1. What is the official source of truth for spend: platform API or agency?
2. What is the official source of truth for business leads: Airtable?
3. What is the exact report timezone for Agency exports?
4. Are Agency date ranges inclusive of the end date?
5. What is the official ad set naming convention?
6. What is the official ad naming convention?
7. Who approves campaign/ad mapping?
8. Who can access PII in Metabase?
9. How long should raw payloads be retained?
10. What alert channel should receive pipeline failures?

---

## 11. Recommended First Engineering Sprint

Sprint goal:

Make Facebook data auditable without breaking the current dashboard.

Scope:

1. Update Facebook extractor fields:
   - `reach`
   - `inline_link_clicks`
   - `actions`
2. Update Pydantic schema:
   - keep `actions_json`
   - parse `website_leads`
   - parse `native_form_leads`
   - parse `platform_leads`
3. Update `raw.facebook_ads` schema additively.
4. Update `task_load_staging`.
5. Update `stg_facebook_ads`.
6. Create `fct_paid_ads_daily`.
7. Add dbt tests.
8. Run backfill for the audit window.
9. Compare Facebook platform numbers vs agency report again.

Expected result:

ATS can answer:

- Which action types did Facebook return?
- How many website leads were reported?
- How many native form leads were reported?
- Which date/campaign/ad caused a discrepancy?
- Did the issue come from platform metrics, agency report, or CRM ingestion gap?

---

## 12. Final Direction

The platform should evolve in this order:

```text
Current Facebook dashboard
    |
    v
Auditable Facebook ad-level fact
    |
    v
Airtable CRM lead current-state fact
    |
    v
Canonical mapping layer
    |
    v
Lead reconciliation mart
    |
    v
Marketing performance mart
    |
    v
Google / TikTok / Zalo integrations
```

The most important rule:

```text
Do not make business decisions from ambiguous leads.
```

Every lead metric must clearly say:

- where it came from
- what it means
- what grain it belongs to
- whether it is platform-reported, CRM-recorded, or business-qualified

