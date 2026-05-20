# ATS Marketing Data Platform

## Project Design Document - Final Draft

**Company:** ATS - Avenue to Success  
**Version:** Final Draft v1.1  
**Date:** 2026-05-20  
**Status:** Architecture approved for implementation planning  
**Scope:** Facebook Ads, Airtable CRM, Agency reports, future Google/TikTok/Zalo expansion

This document replaces the earlier `ATS_Marketing_Pipeline_Design_v1.0.docx` as the practical architecture direction for the current project state. The previous document remains valuable as the original production design reference, especially for ELT principles, observability, idempotency, and edge cases. This final draft updates the design based on the actual ATS operating model, current Facebook pipeline, Airtable lead retainer, Agency reconciliation needs, and future multi-platform requirements.

---

# 1. Project Overview

## 1.1 Background

ATS runs paid marketing campaigns across Facebook today and plans to scale reporting across Google Ads, TikTok Ads, and Zalo Ads. Marketing leads are operationally managed in Airtable through the ATS lead retainer and counselor workflow.

The current system already has a working Facebook pipeline:

```text
Facebook Ads API
  -> Airflow
  -> MinIO raw JSON backup
  -> PostgreSQL raw.facebook_ads
  -> dbt staging/mart
  -> Metabase dashboard
```

This is a strong starting point, but the system currently behaves more like a Facebook reporting pipeline than a full marketing data platform.

The key production problem is no longer only "can we pull data?". The harder problem is:

```text
Can ATS trust the number?
Can ATS explain why Facebook, Agency, and Airtable disagree?
Can ATS tell which campaigns produce valid leads and real business outcomes?
Can the model scale to Google, TikTok, Zalo, and CRM quality?
```

## 1.2 Business Goals

The platform must support three levels of decision making:

1. **Executive view**
   - Total spend
   - Total leads
   - Valid leads
   - Event attendance
   - Office performance
   - Platform efficiency

2. **Marketing manager view**
   - Campaign performance
   - CPL by platform/campaign/office
   - Lead quality by source
   - Spend efficiency
   - Underperforming campaigns
   - Agency/platform discrepancy

3. **Operations and data view**
   - Pipeline health
   - Missing mappings
   - Duplicate leads
   - Invalid/wrong number rates
   - Platform vs CRM mismatch
   - Agency report mismatch

## 1.3 Primary Business Funnel

ATS lead lifecycle:

```text
Ad
  -> Form Submit
  -> CRM Record in Airtable
  -> Telesales Call
  -> Quality + Rating + Invite Event
  -> Wrong number / Invalid -> Drop
  -> Valid / Keep Following / Valid but No -> Counselor Assigned
  -> Follow-up
  -> Event path: Confirm Event -> Attend Event -> Deep Consultation -> Apply -> Enroll
  -> Non-event path: Profile Consultation -> Apply -> Enroll
```

This means the platform cannot stop at `platform_leads`. Platform-reported leads are useful, but ATS business value is created later in the funnel through Airtable quality, counselor follow-up, event attendance, application, and enrollment.

## 1.4 Scope

| Area | In Scope V1 | Later Phase |
| --- | --- | --- |
| Ad platforms | Facebook Ads | Google Ads, TikTok Ads, Zalo Ads |
| CRM | Airtable lead retainer current state | Airtable history/snapshots, counselor touchpoints |
| Agency report | Facebook Ads Manager export | Automated Google Sheet ingestion |
| Data warehouse | PostgreSQL | Same unless scale demands change |
| Transform | dbt Core | Same |
| Orchestration | Airflow | Same |
| Dashboard | Metabase | Same |
| Attribution | Name-based mapping with canonical identity | ID/UTM-based attribution when tracking improves |
| Reconciliation | Facebook vs Agency vs Airtable | Multi-platform reconciliation |

---

# 2. Architecture

## 2.1 Current Architecture

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
dw.fct_ad_spend
    |
    v
Metabase
```

Current strengths:

- Airflow orchestration already exists.
- Facebook daily DAG exists.
- Facebook backfill DAG exists.
- MinIO raw backup exists.
- PostgreSQL warehouse exists.
- dbt models and tests exist.
- CI/CD exists.
- Metabase is connected.

Current limitations:

- Facebook `actions` are requested but not stored in Postgres.
- `leads` is compressed into one ambiguous metric.
- `website_leads` and `native_form_leads` are not separated.
- `reach` and `link_clicks` are missing.
- Current `fct_ad_spend` is not ad-level enough for full reconciliation.
- Airtable CRM is not integrated.
- Agency reports are not modeled as data.
- No mapping layer exists for formatted campaign names.
- No reconciliation mart exists.

## 2.2 Target Architecture

```text
                 +---------------------+
                 | Facebook Ads API    |
                 +---------------------+
                           |
                 +---------------------+
                 | Google Ads API      |
                 +---------------------+
                           |
                 +---------------------+
                 | TikTok Ads API      |
                 +---------------------+
                           |
                 +---------------------+
                 | Zalo Ads API        |
                 +---------------------+
                           |
                 +---------------------+
                 | Airtable CRM API    |
                 +---------------------+
                           |
                 +---------------------+
                 | Agency Reports      |
                 +---------------------+
                           |
                           v
+------------------------------------------------------+
| Raw Layer                                             |
| raw.facebook_ads                                      |
| raw.google_ads                                        |
| raw.tiktok_ads                                        |
| raw.zalo_ads                                          |
| raw.airtable_leads                                    |
| raw.agency_facebook_report                            |
+------------------------------------------------------+
                           |
                           v
+------------------------------------------------------+
| Staging Layer                                         |
| stg_facebook_ads                                      |
| stg_google_ads                                        |
| stg_tiktok_ads                                        |
| stg_zalo_ads                                          |
| stg_airtable_leads                                    |
| stg_agency_facebook_report                            |
+------------------------------------------------------+
                           |
                           v
+------------------------------------------------------+
| Identity and Mapping Layer                            |
| map_marketing_entity_identity                         |
| dim_campaign                                          |
| dim_ad_set                                            |
| dim_ad                                                |
| dim_office                                            |
| dim_platform                                          |
| dim_date                                              |
+------------------------------------------------------+
                           |
                           v
+------------------------------------------------------+
| Intermediate / Normalized Layer                       |
| int_paid_ads_normalized                               |
| int_crm_leads_normalized                              |
| int_agency_report_normalized                          |
+------------------------------------------------------+
                           |
                           v
+------------------------------------------------------+
| Mart Layer                                            |
| fct_paid_ads_daily                                    |
| fct_crm_leads_current                                 |
| fct_marketing_performance_daily                       |
| fct_lead_reconciliation_daily                         |
| fct_data_quality_daily                                |
+------------------------------------------------------+
                           |
                           v
+------------------------------------------------------+
| Metabase Dashboards                                   |
| Executive Overview                                    |
| Marketing Performance                                 |
| Lead Quality                                          |
| Reconciliation / Debug                                |
| Data Quality / Operations                             |
+------------------------------------------------------+
```

## 2.3 Why This Architecture

This architecture separates concerns clearly:

| Layer | Responsibility | Why It Exists |
| --- | --- | --- |
| Raw | Store source data close to original | Allows audit and reprocessing |
| Staging | Rename, cast, normalize basic types | Keeps source cleaning simple and testable |
| Mapping | Resolve identity across systems | Prevents wrong joins from formatted names |
| Intermediate | Normalize platform-specific metrics | Allows Facebook, Google, TikTok, Zalo to share one mart |
| Mart | Business-ready facts | Powers dashboards and decisions |
| Reconciliation | Explain mismatches | Converts disputes into traceable data checks |

The most important design choice is the mapping layer. Airtable currently does not store `campaign_id`, `adset_id`, `ad_id`, `fbclid`, `gclid`, or UTM fields. Campaign/ad names can be formatted before entering ATS reporting. Therefore, direct joins by campaign name are unsafe.

---

# 3. Core Design Principles

## 3.1 Raw Data Must Be Auditable

The system must preserve enough raw source detail to explain future discrepancies.

For Facebook this means storing:

```text
actions_json
reach
link_clicks
website_leads
native_form_leads
platform_leads
```

Reason:

If Facebook reports one lead number, Agency reports another, and Airtable shows another, ATS needs to inspect which action types Facebook returned. A single `leads` column is not enough.

## 3.2 Names Are Display Fields, Not Keys

Campaign names are not reliable identifiers.

Examples:

```text
Facebook: FB_MayFair2026_2026Q2_Mix_26.ATS.03
Airtable: May Fair 2026 - Mix - ATS 03
Agency: MayFair2026 Q2 Mix ATS03
```

These can refer to the same business campaign. Therefore, the platform needs canonical keys:

```text
canonical_campaign_key
canonical_ad_set_key
canonical_ad_key
```

Reason:

If names are used directly for joins, wrong mappings will silently corrupt CPL, quality rate, and reconciliation.

## 3.3 Platform Leads And Business Leads Are Different

Platform leads:

```text
Facebook website leads
Facebook native form leads
Google conversions
TikTok leads
Zalo leads
```

Business leads:

```text
Airtable CRM record
Valid lead
Qualified lead
Event confirmed lead
Event attended lead
Application
Enrollment
```

Reason:

Facebook optimizes campaign delivery, but Airtable represents ATS operational truth. Marketing should eventually optimize for valid/qualified/event-attended leads, not only platform-reported leads.

## 3.4 Keep Invalid Data, But Do Not Count It As Valid

`Wrong number` and `Invalid` should not be deleted.

They should be included in:

```text
lead_submissions
crm_leads
invalid_leads
wrong_number_leads
```

They should be excluded from:

```text
valid_leads
qualified_leads
cpl_valid denominator
```

Reason:

Invalid leads are still a marketing cost and data quality signal. Removing them hides campaign quality problems.

## 3.5 Build Current State First, Then History

Airtable has UI logs, but history extraction may be complex.

V1:

```text
fct_crm_leads_current
```

V2:

```text
fct_crm_lead_status_history
crm snapshots
touchpoint history
```

Reason:

Current-state reporting gives business value quickly. History can be added once the base CRM model is reliable.

---

# 4. Data Model

## 4.1 Schemas

| Schema | Purpose | Example Tables |
| --- | --- | --- |
| `raw` | Source-aligned data, staging buffers, raw payload columns | `facebook_ads`, `airtable_leads`, `agency_facebook_report` |
| `dw` | Data warehouse facts, dims, marts | `fct_paid_ads_daily`, `fct_crm_leads_current`, `dim_campaign` |
| `meta` | Observability and operational logs | `pipeline_runs`, `data_quality_log`, `schema_versions` |

The existing project already uses `raw`, `dw`, and `meta`. The final architecture keeps this structure.

## 4.2 Entity Relationship Overview

```text
                  dim_platform
                       |
                       v
raw.facebook_ads -> stg_facebook_ads -> int_paid_ads_normalized -> fct_paid_ads_daily
                                                           |
                                                           v
                                               fct_marketing_performance_daily
                                                           ^
                                                           |
raw.airtable_leads -> stg_airtable_leads -> fct_crm_leads_current
                                                           ^
                                                           |
raw.agency_report -> stg_agency_report -> fct_lead_reconciliation_daily

map_marketing_entity_identity links:
  platform raw names / IDs
  agency names
  Airtable formatted names
  canonical campaign/ad set/ad identities
```

## 4.3 Raw Facebook Ads

Table:

```text
raw.facebook_ads
```

Grain:

```text
date + account_id + campaign_id + ad_set_id + ad_id
```

Recommended columns:

| Column | Type | Description |
| --- | --- | --- |
| `account_id` | text | Facebook ad account ID |
| `campaign_id` | text | Facebook campaign ID |
| `campaign_name` | text | Raw Facebook campaign name |
| `ad_set_id` | text | Facebook ad set ID |
| `ad_set_name` | text | Raw Facebook ad set name |
| `ad_id` | text | Facebook ad ID |
| `ad_name` | text | Raw Facebook ad name |
| `date` | date | Facebook reporting date |
| `spend` | numeric | Spend |
| `impressions` | bigint | Impressions |
| `reach` | bigint | Reach |
| `clicks` | bigint | All clicks |
| `link_clicks` | bigint | Link clicks / inline link clicks |
| `actions_json` | jsonb | Raw Facebook actions array |
| `website_leads` | int | Leads from website/pixel-related actions |
| `native_form_leads` | int | Leads from Facebook native lead forms |
| `platform_leads` | int | Website + native form leads |
| `loaded_at` | timestamptz | Warehouse load time |

Why this design:

- Keeps raw names and IDs for audit.
- Keeps `actions_json` so lead parsing can be inspected later.
- Splits lead metrics for reconciliation with Agency columns: `Website leads` and `On-Facebook leads`.
- Adds `link_clicks` because Agency reports link clicks, while Facebook `clicks` is broader.
- Adds `reach` because Agency report includes reach.

Migration strategy:

- Add columns additively.
- Do not remove existing `leads` column immediately.
- Keep old dashboard alive while new mart is built.

## 4.4 Staging Facebook Ads

Model:

```text
stg_facebook_ads
```

Responsibilities:

- Cast dates and numeric fields.
- Normalize nulls.
- Keep source fields.
- Expose split lead metrics.

Not allowed:

- No business mapping.
- No joins to Airtable.
- No final CPL logic.

Reason:

Staging should be predictable. If business logic is pushed into staging, future changes become risky.

## 4.5 Raw Airtable Leads

Table:

```text
raw.airtable_leads
```

Grain:

```text
record_id
```

Recommended columns:

| Column | Description |
| --- | --- |
| `record_id` | Airtable record ID, primary natural key |
| `campaign` | Raw/formatted campaign field from Airtable |
| `attend_event` | Actual event attendance/check-in |
| `family_name` | PII |
| `given_name` | PII |
| `phone` | PII |
| `email` | PII |
| `counselors` | Assigned counselor |
| `moved_to_counselor_report` | Telesales-to-counselor stage flag |
| `note_by_telesales` | Telesales note |
| `last_update_l` | Manual counselor update field |
| `ad_name` | Raw/formatted ad name |
| `ad_set_name` | Raw/formatted ad set name |
| `ads_platform` | Filled by ATS |
| `counselors_follow_up_note` | Counselor follow-up notes |
| `source_of_leads` | Lead source |
| `office_location` | Office |
| `time_to_study_abroad` | Study abroad timeline |
| `role` | Student/parent/other role |
| `quality` | Telesales quality result |
| `checked_phone_no_already` | Phone check flag |
| `tracking_date` | Date lead entered Airtable/system |
| `rating_by_counselors` | Counselor rating |
| `event_location` | Event location |
| `confirmation_to_attend_event` | Confirmed event intent |
| `raw_payload_json` | Full raw Airtable record |
| `loaded_at` | Load time |

Why this design:

- `record_id` is the stable CRM key.
- Raw names are preserved because Airtable names may be formatted.
- PII is kept only where needed and should be controlled.
- `raw_payload_json` protects against Airtable schema drift.
- `tracking_date` represents the date the lead entered the ATS system, which is necessary for CRM daily reporting.

## 4.6 Staging Airtable Leads

Model:

```text
stg_airtable_leads
```

Responsibilities:

- Rename fields into snake_case.
- Parse dates.
- Normalize quality values.
- Create `phone_hash` and `email_hash`.
- Preserve raw names.
- Create basic boolean flags.

Recommended derived fields:

```text
phone_hash
email_hash
lead_identity_key
normalized_campaign_name
normalized_ad_set_name
normalized_ad_name
quality_normalized
is_valid_lead
is_qualified_lead
is_invalid
is_wrong_number
is_keep_following
is_valid_but_no
```

Why hash phone/email:

- Phone/email are needed for deduplication.
- Dashboards should not expose PII broadly.
- Hashing supports identity matching with reduced PII exposure.

## 4.7 Agency Facebook Report

Table:

```text
raw.agency_facebook_report
```

Expected grain:

```text
date + campaign_name + ad_set_name + ad_name
```

Expected columns:

```text
date
campaign_name
ad_set_name
ad_name
impressions
reach
link_clicks
website_leads
on_facebook_leads
cost
report_source
report_timezone
attribution_setting
loaded_at
```

Known setting:

```text
source = Facebook Ads Manager
attribution_setting = 1-day click
```

Still needed:

```text
timezone
whether date range includes end date
whether export grain is always ad-level
```

Why model Agency reports:

Agency numbers are part of the operational reconciliation process. They should not live only in screenshots or copied notes.

## 4.8 Marketing Entity Mapping

Table:

```text
dw.map_marketing_entity_identity
```

Purpose:

Map source-specific names and IDs into canonical ATS business entities.

Recommended columns:

| Column | Description |
| --- | --- |
| `entity_type` | `campaign`, `ad_set`, `ad` |
| `source_system` | `facebook`, `airtable`, `agency`, `google`, `tiktok`, `zalo` |
| `source_platform` | Ad platform |
| `source_account_id` | Platform account ID if available |
| `source_campaign_id` | Source campaign ID if available |
| `source_ad_set_id` | Source ad set ID if available |
| `source_ad_id` | Source ad ID if available |
| `source_campaign_name` | Raw source campaign name |
| `source_ad_set_name` | Raw source ad set name |
| `source_ad_name` | Raw source ad name |
| `normalized_source_key` | Text-normalized matching helper |
| `canonical_campaign_key` | Approved campaign identity |
| `canonical_campaign_name` | Business campaign display name |
| `canonical_ad_set_key` | Approved ad set identity |
| `canonical_ad_set_name` | Business ad set display name |
| `canonical_ad_key` | Approved ad identity |
| `canonical_ad_name` | Business ad display name |
| `mapping_status` | `suggested`, `approved`, `rejected`, `unmapped` |
| `mapping_confidence` | Numeric confidence for suggested match |
| `mapped_by` | Person/system approving mapping |
| `mapped_at` | Approval timestamp |
| `notes` | Manual notes |

Why this design:

- Airtable currently has no platform IDs or UTM fields.
- Campaign/ad names are formatted for business use.
- Mapping must be reviewable, not hidden inside SQL.
- Unmapped rows must become visible data quality issues.

Production rule:

```text
Business dashboards use approved mappings.
Unmapped rows appear in data quality dashboards.
No silent joins by raw name.
```

## 4.9 Dimensions

### `dim_platform`

```text
platform_key
platform_name
is_paid_platform
default_timezone
default_currency
```

Reason:

Supports Facebook, Google, TikTok, Zalo, organic, and future sources.

### `dim_campaign`

```text
canonical_campaign_key
canonical_campaign_name
platform
school_or_market
year_quarter
objective
campaign_group
office_scope
start_date
end_date
is_active
mapping_status
updated_at
```

Reason:

Separates business campaign identity from source names.

### `dim_ad_set`

```text
canonical_ad_set_key
canonical_campaign_key
canonical_ad_set_name
office
audience
targeting_group
updated_at
```

Reason:

Office is often more reliable at ad set level than campaign level, especially when a campaign targets multiple offices.

### `dim_ad`

```text
canonical_ad_key
canonical_ad_set_key
canonical_ad_name
asset
creative_type
message_angle
updated_at
```

Reason:

Ad-level grain is needed for Agency reconciliation and creative performance.

### `dim_office`

```text
office_key
office_name
city
region
is_active
```

Known values:

```text
HCM
HN
DN
ALL
HCMTinh
HNTinh
DNTinh
UNKNOWN
```

### `dim_date`

Standard calendar dimension for daily, weekly, monthly, quarter reporting.

Reason:

Improves dashboard consistency and time grouping.

## 4.10 Fact: Paid Ads Daily

Table:

```text
dw.fct_paid_ads_daily
```

Grain:

```text
date + platform + account_id + campaign_id + ad_set_id + ad_id
```

Recommended columns:

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
office
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

Why this grain:

- Agency report includes `Ad name`.
- Facebook API can return ad-level insights.
- Future creative/ad performance requires ad-level data.
- Aggregating too early destroys the ability to debug discrepancies.

Why not replace old `fct_ad_spend` immediately:

- Current dashboards depend on it.
- A migration should be additive.
- The old table can remain as a compatibility/reporting layer until dashboards move to the new fact.

## 4.11 Fact: CRM Leads Current

Table:

```text
dw.fct_crm_leads_current
```

Grain:

```text
record_id
```

Recommended columns:

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
is_duplicate_event
attend_event
confirmation_to_attend_event
moved_to_counselor_report
counselor
office_location
event_location
loaded_at
```

Quality mapping V1:

| Quality | `is_valid_lead` | `is_qualified_lead` | Business Interpretation |
| --- | --- | --- | --- |
| `Valid` | true | true | Strong lead |
| `Valid but No` | true | false | Real/valid person, currently negative or not ready |
| `Keep following` | true | false | Has interest, but not ideal market/timing |
| `Invalid` | false | false | Not valid |
| `Wrong number` | false | false | Invalid contact |

Why this design:

- Airtable is ATS operational truth.
- `record_id` is stable.
- Phone/email hashes enable dedupe.
- Raw names are preserved for audit.
- Canonical keys enable campaign reporting after mapping.
- Invalid leads are retained as quality signals.

## 4.12 Duplicate Logic

ATS needs multiple duplicate definitions, not one:

| Duplicate Type | Definition | Usage |
| --- | --- | --- |
| `duplicate_person` | Same phone/email across all records | Unique people reporting |
| `duplicate_campaign` | Same phone/email within same campaign | Campaign quality and CPL |
| `duplicate_event` | Same phone/email for same event | Event registration quality |

Known business rule:

```text
If one person registers for multiple events, they are the same person,
but should still count for the event/campaign they registered for.
They should not be counted repeatedly inside the same campaign.
```

Metrics created from this:

```text
lead_submissions
unique_people
unique_people_by_campaign
valid_leads
unique_valid_people
duplicate_leads
```

Reason:

One duplicate flag cannot support both marketing attribution and CRM operations.

## 4.13 Fact: Marketing Performance Daily

Table:

```text
dw.fct_marketing_performance_daily
```

Suggested grain:

```text
date + platform + canonical_campaign_key + office
```

Recommended columns:

```text
date
platform
canonical_campaign_key
canonical_campaign_name
office
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
invalid_leads
wrong_number_leads
duplicate_leads
cpl_platform
cpl_crm
cpl_valid
lead_to_valid_rate
lead_to_event_confirm_rate
lead_to_event_attend_rate
updated_at
```

Why this model:

- This is the main business dashboard table.
- It separates platform performance from CRM quality.
- It supports office/campaign/platform decisions.
- It avoids making Metabase perform complex joins repeatedly.

Important date caveat:

Ads date and Airtable `tracking_date` may not always represent the same business moment.

V1 can report CRM by `tracking_date`, but reconciliation should clearly label:

```text
ad_reporting_date
crm_tracking_date
```

## 4.14 Fact: Lead Reconciliation Daily

Table:

```text
dw.fct_lead_reconciliation_daily
```

Suggested grain:

```text
date + platform + canonical_campaign_key + canonical_ad_set_key + canonical_ad_key
```

Recommended columns:

```text
date
platform
campaign_name
ad_set_name
ad_name
canonical_campaign_key
canonical_ad_set_key
canonical_ad_key
mapping_status
platform_website_leads
platform_native_form_leads
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

Reconciliation statuses:

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

Why this model:

This table exists for dispute resolution and debugging. It answers:

- Which date is wrong?
- Which campaign/ad is wrong?
- Is the issue platform data, agency export, CRM ingestion, or mapping?

---

# 5. Pipeline Design

## 5.1 Facebook Pipeline

Current pipeline should be upgraded, not replaced.

Required extractor fields:

```text
campaign_id
campaign_name
adset_id
adset_name
ad_id
ad_name
date_start
spend
impressions
reach
clicks
inline_link_clicks
actions
```

Load process:

```text
Extract -> MinIO raw JSON -> Validate -> raw.facebook_ads -> dbt staging -> dbt mart
```

Production requirements:

- Retry transient Facebook errors.
- Treat rate limit code `4` as retryable/throttling.
- Use chunked backfill.
- Use rolling lookback window.
- Keep raw JSON in MinIO.
- Store `actions_json` in Postgres.

## 5.2 Airtable CRM Pipeline

Pipeline:

```text
Airtable API
  -> Airflow DAG
  -> MinIO raw JSON
  -> raw.airtable_leads
  -> stg_airtable_leads
  -> fct_crm_leads_current
```

V1 extraction requirements:

- Pull `record_id`.
- Pull all lead retainer fields.
- Pull created/modified metadata if available.
- Store raw payload.
- Reprocess recent records because quality and notes change after initial creation.

Why rolling reprocess is needed:

Telesales and counselors update quality, notes, event confirmation, and follow-up after the lead enters Airtable.

## 5.3 Agency Report Pipeline

V1 can start manually:

```text
Agency CSV/Markdown/Sheet
  -> raw.agency_facebook_report
  -> stg_agency_facebook_report
  -> fct_lead_reconciliation_daily
```

Later:

```text
Google Sheet connector or scheduled file ingestion
```

Production contract required:

```text
Date
Campaign name
Ad set name
Ad name
Impressions
Reach
Link clicks
Website leads
On-Facebook leads
Cost
Timezone
Attribution setting
Exported at
```

## 5.4 Multi-Platform Extension

For each new platform:

```text
raw.<platform>_ads
stg_<platform>_ads
int_paid_ads_normalized
fct_paid_ads_daily
```

Platform-specific fields stay in staging. Shared business fields flow into the normalized mart:

```text
spend
impressions
reach
clicks
link_clicks
website_leads
native_form_leads
platform_leads
conversions
```

Reason:

The dashboard should not be rewritten every time a new platform is added.

---

# 6. Implementation Phases

## Phase 1 - Protect Current Reporting

Goal:

Keep the existing Facebook dashboard working while adding auditability.

Tasks:

1. Do not remove current `fct_ad_spend`.
2. Add new columns to raw/staging additively.
3. Keep current Metabase cards alive.
4. Add dbt tests for new columns.

Why first:

Current reporting is already useful. Migration should not break production visibility.

## Phase 2 - Upgrade Facebook Observability

Goal:

Make Facebook data auditable.

Tasks:

1. Request `reach`, `inline_link_clicks`, `actions`.
2. Store `actions_json`.
3. Parse:
   - `website_leads`
   - `native_form_leads`
   - `platform_leads`
4. Add retry support for rate limit code `4`.
5. Backfill audit window.

Why second:

The current lead discrepancy cannot be explained without action-level raw payload.

## Phase 3 - Build Ad-Level Paid Ads Fact

Goal:

Create the normalized ad-level fact for Facebook and future platforms.

Tasks:

1. Create `fct_paid_ads_daily`.
2. Use grain:
   ```text
   date + platform + account_id + campaign_id + ad_set_id + ad_id
   ```
3. Keep old `fct_ad_spend`.
4. Add unique grain tests.
5. Add non-negative metric tests.

Why third:

Agency report has ad names. Reconciliation needs ad-level grain.

## Phase 4 - Build Airtable CRM Current-State Model

Goal:

Bring ATS operational truth into the warehouse.

Tasks:

1. Create `raw.airtable_leads`.
2. Create Airtable extractor.
3. Create `stg_airtable_leads`.
4. Hash phone/email.
5. Normalize quality values.
6. Add duplicate flags.
7. Create `fct_crm_leads_current`.

Why fourth:

CRM lead quality is the business target. Without it, dashboard only shows ad platform activity.

## Phase 5 - Build Mapping Layer

Goal:

Prevent wrong joins between Ads, Airtable, and Agency.

Tasks:

1. Create `map_marketing_entity_identity`.
2. Build normalized name helper.
3. Generate suggested mappings.
4. Add manual approval status.
5. Flag unmapped rows.

Why fifth:

Airtable has formatted names and no ad IDs. Mapping is mandatory before joining CRM and Ads for business reporting.

## Phase 6 - Build Reconciliation Mart

Goal:

Explain discrepancies between platform, agency, and CRM.

Tasks:

1. Model agency report.
2. Join platform and agency by approved canonical mapping.
3. Join CRM leads by approved canonical mapping.
4. Create discrepancy columns.
5. Create reconciliation statuses.

Why sixth:

This directly addresses the current real business problem: lead count mismatch.

## Phase 7 - Build Marketing Performance Mart

Goal:

Create the main decision table for dashboards.

Tasks:

1. Create `fct_marketing_performance_daily`.
2. Add CPL metrics:
   - `cpl_platform`
   - `cpl_crm`
   - `cpl_valid`
3. Add funnel rates.
4. Add office/campaign/platform grouping.
5. Build Executive and Marketing dashboards.

## Phase 8 - Add Google, TikTok, Zalo

Goal:

Scale the platform.

Tasks per platform:

1. Extract raw ads data.
2. Create staging model.
3. Map native metrics to normalized fields.
4. Add to `fct_paid_ads_daily`.
5. Add reconciliation if reports exist.

---

# 7. Data Quality and Tests

## 7.1 dbt Tests

Required tests:

```text
not_null keys
unique grain
spend >= 0
impressions >= 0
clicks >= 0
link_clicks >= 0
platform_leads >= 0
valid_leads >= 0
date not null
accepted_values for platform
accepted_values for quality
accepted_values for mapping_status
```

## 7.2 Data Quality Metrics

Daily checks:

```text
unmapped_ads_rows
unmapped_crm_leads
duplicate_leads
wrong_number_rate
invalid_rate
platform_vs_agency_diff
platform_vs_crm_diff
crm_freshness_hours
ads_freshness_hours
```

## 7.3 Failure Handling

| Failure | Strategy |
| --- | --- |
| Facebook rate limit | Retry with exponential backoff, chunk backfills |
| Facebook API transient error | Retry |
| Airtable API timeout | Retry, keep previous CRM mart |
| Agency file missing | Mark reconciliation as `MISSING_AGENCY_REPORT` |
| Mapping missing | Mark rows `UNMAPPED`, do not silently join |
| dbt test failure | Fail pipeline and alert |
| data stale | Alert after SLA threshold |

---

# 8. Dashboard Specification

## 8.1 Executive Overview

Audience:

```text
Management
Marketing manager
```

Metrics:

```text
total_spend
platform_leads
crm_leads
valid_leads
qualified_leads
event_confirmed_leads
event_attended_leads
cpl_platform
cpl_crm
cpl_valid
office performance
platform performance
```

Default behavior:

- Exclude today unless explicitly selected.
- Show `data_finalized_through`.
- Use business metrics from `fct_marketing_performance_daily`.

## 8.2 Marketing Performance Dashboard

Audience:

```text
Marketing manager
Marketing executive
```

Views:

```text
campaign ranking
daily spend vs leads
CPL by platform
CPL by campaign
lead quality by campaign
invalid/wrong number rate
office comparison
```

## 8.3 Lead Quality Dashboard

Audience:

```text
Telesales manager
Counselor manager
Data/Ops
```

Views:

```text
quality distribution
valid lead rate
wrong number rate
duplicate lead rate
counselor assignment rate
event confirmation rate
event attendance rate
```

## 8.4 Reconciliation Dashboard

Audience:

```text
Marketing manager
Data/Ops
Agency discussion
```

Views:

```text
platform vs agency leads
platform vs CRM leads
agency vs CRM leads
date-level discrepancy
campaign/ad-level discrepancy
missing mapping
missing agency rows
```

This dashboard is for debugging, not executive storytelling.

---

# 9. Security and PII

PII fields:

```text
family_name
given_name
phone
email
notes
```

Recommended controls:

1. Store phone/email only where operationally required.
2. Create `phone_hash` and `email_hash` for dedupe.
3. Use hashed fields in dashboards where possible.
4. Restrict Metabase access to PII collections.
5. Do not commit `.env`, notes with credentials, or raw CRM exports.
6. Rotate exposed tokens.

Reason:

Marketing reporting rarely needs direct phone/email. Dedupe and performance analysis can use hashed identities.

---

# 10. Production Risks and Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Campaign names differ between Ads/Airtable/Agency | High | Canonical mapping layer |
| Airtable does not store platform IDs | High | Mapping now, improve tracking later |
| Single `leads` metric is ambiguous | High | Split platform, website, native form, CRM, valid leads |
| Facebook attribution updates historical data | Medium | Rolling lookback and upsert |
| Agency exports use different settings | Medium | Store attribution/timezone/export metadata |
| Duplicate CRM leads inflate performance | High | phone/email hash and duplicate flags |
| Invalid leads hidden from CPL | Medium | Keep invalids, report separate CPLs |
| API rate limits break backfills | Medium | Chunked backfill and retry |
| PII exposed in dashboard | High | Hash/mask/restrict access |
| Mapping mistakes corrupt business mart | High | mapping status and manual approval |
| Airtable updates overwrite history | Medium | current-state V1, snapshots V2 |

---

# 11. Open Questions Before Production V1

These are not blockers for Phase 1, but should be answered before production sign-off:

1. What timezone does Agency export use?
2. Is Agency report date range inclusive of the end date?
3. Is Agency report always ad-level?
4. Who approves mapping records?
5. What are the official ad set naming rules?
6. What are the official ad naming rules?
7. What are all valid office codes?
8. Should `Keep following` count as qualified or only valid?
9. Who can see PII in Metabase?
10. How many days should Airtable records be reprocessed?
11. How long should raw CRM payloads be retained?
12. What alert channel should receive pipeline failures?
13. Are application and enrollment data available in Airtable or another system?
14. Will future forms capture campaign/ad IDs or UTMs?

---

# 12. Final Recommendation

The platform should be built in this order:

```text
1. Keep current Facebook dashboard stable
2. Upgrade Facebook raw observability
3. Create ad-level fct_paid_ads_daily
4. Extract Airtable CRM leads
5. Build CRM current-state fact
6. Build canonical mapping layer
7. Build reconciliation mart
8. Build marketing performance mart
9. Add Google/TikTok/Zalo
10. Add CRM history and deeper funnel outcomes
```

The most important architecture decision is:

```text
Do not join systems by raw campaign name.
Use canonical mapping keys.
```

The most important metric decision is:

```text
Do not use one ambiguous leads column.
Separate platform_leads, crm_leads, valid_leads, and qualified_leads.
```

The most important production decision is:

```text
Keep raw payloads and make mismatches visible.
Do not silently hide unmapped, invalid, duplicate, or discrepant data.
```

This design gives ATS a path from the current Facebook reporting pipeline to a scalable marketing data platform that can support paid media, CRM quality, Agency reconciliation, and future platform expansion.

