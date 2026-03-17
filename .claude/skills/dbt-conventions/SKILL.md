---
name: dbt-conventions
description: Apply when writing, fixing, or reviewing any dbt model, schema.yml,
  test, macro, or source definition. Auto-invoked for any file in dbt/models/
  or dbt/tests/, schema.yml, SQL in dbt directory, incremental models,
  UPSERT patterns, staging/intermediate/fact/dim/report models, dbt test
  additions, dbt model reviews, fixing dbt bugs, SQL models, transforms.
  Also triggers on: fix dbt, model failing, test failing, SQL model,
  transform data, select from, ref model, source definition.
allowed-tools: Read, Write, Bash(dbt *)
---

# dbt Conventions — DE Senior Standard

## Current model status (live):
!`find dbt/models -name "*.sql" 2>/dev/null | sort | sed 's|dbt/models/||' || echo "No models yet"`

## Packages installed:
!`cat dbt/packages.yml 2>/dev/null || echo "Run: dbt deps"`

## Recent test results:
!`cd dbt && dbt test --quiet 2>&1 | grep -E "(PASS|FAIL|ERROR|Warning)" | tail -8 2>/dev/null || echo "Run dbt test to see results"`

---

## Model naming (strict)

| Prefix | Layer | Location | Rule |
|--------|-------|----------|------|
| `stg_` | Staging | `models/staging/` | 1-to-1 source, rename + cast only |
| `int_` | Intermediate | `models/intermediate/` | Joins, enrichment |
| `fct_` | Fact | `models/marts/` | Additive metrics, UPSERT-safe |
| `dim_` | Dimension | `models/dimensions/` | Descriptive, SCD2 |
| `rpt_` | Report | `models/marts/` | Pre-aggregated for Metabase |

## Incremental UPSERT pattern (ALL fct_ models)

```sql
{{ config(
    materialized='incremental',
    unique_key=['date', 'platform', 'campaign_id', 'ad_set_id'],
    on_schema_change='fail'
) }}

SELECT ...
FROM {{ ref('stg_facebook_ads') }}
{% if is_incremental() %}
-- EC-06: lookback 7 days for retroactive attribution
WHERE date >= (SELECT MAX(date) - INTERVAL '7 days' FROM {{ this }})
{% endif %}
```

## Minimum tests per model

```yaml
tests:
  - unique:
      column_name: "date || '_' || platform || '_' || campaign_id"
  - dbt_utils.expression_is_true:
      expression: "spend >= 0"
  - dbt_utils.expression_is_true:
      expression: "leads >= 0"
  - dbt_utils.recency:
      datepart: hour
      field: updated_at
      interval: 25
```

## After writing every model — mandatory

```bash
dbt compile --select [model_name]
dbt run --select [model_name]
dbt test --select [model_name]
```


## Model naming (strict — no exceptions)

| Prefix | Layer | Location | Rule |
|--------|-------|----------|------|
| `stg_` | Staging | `models/staging/` | 1-to-1 source, rename + cast only |
| `int_` | Intermediate | `models/intermediate/` | Joins, enrichment, business logic |
| `fct_` | Fact | `models/marts/` | Additive metrics, UPSERT-safe |
| `dim_` | Dimension | `models/dimensions/` | Descriptive, SCD2 where needed |
| `rpt_` | Report | `models/marts/` | Pre-aggregated for Metabase |

## Staging model pattern (stg_*)

```sql
-- models/staging/stg_facebook_ads.sql
-- Rule: ONLY rename, cast, light clean. No joins. No business logic.

with source as (
    select * from {{ source('raw', 'facebook_ads') }}
),

renamed as (
    select
        -- identifiers
        campaign_id::text                           as campaign_id,
        campaign_name::text                         as campaign_name,
        ad_set_id::text                             as ad_set_id,
        ad_id::text                                 as ad_id,

        -- dimensions
        date::date                                  as date,
        'facebook'::text                            as platform,

        -- metrics (cast + validate non-negative)
        greatest(spend::numeric(12,2), 0)           as spend,
        greatest(impressions::bigint, 0)            as impressions,
        greatest(clicks::bigint, 0)                 as clicks,
        greatest(leads::int, 0)                     as leads,

        -- metadata
        _loaded_at::timestamptz                     as loaded_at

    from source
)

select * from renamed
```

## Fact model pattern (fct_*) — incremental UPSERT

```sql
-- models/marts/fct_ad_spend.sql
{{ config(
    materialized='incremental',
    unique_key=['date', 'platform', 'campaign_id', 'ad_set_id'],
    on_schema_change='fail',
    partition_by={'field': 'date', 'data_type': 'date', 'granularity': 'month'},
    indexes=[{'columns': ['date', 'platform'], 'type': 'btree'}]
) }}

with spend as (
    select * from {{ ref('stg_facebook_ads') }}
    {% if is_incremental() %}
    -- EC-06: lookback 7 days for retroactive attribution updates
    where date >= (select max(date) - interval '7 days' from {{ this }})
    {% endif %}
)

select
    date,
    platform,
    campaign_id,
    campaign_name,
    ad_set_id,

    -- EC-10: extract office from campaign name
    case
        when split_part(campaign_name, '_', 3) in ('HCM', 'HN', 'DN')
        then split_part(campaign_name, '_', 3)
        else 'UNKNOWN'
    end                                     as office,

    sum(spend)                              as spend,
    sum(impressions)                        as impressions,
    sum(clicks)                             as clicks,
    sum(leads)                              as leads,

    -- derived (safe division)
    case when sum(leads) > 0
         then sum(spend) / sum(leads)
         else null
    end                                     as cpl,

    now()                                   as updated_at

from spend
group by 1, 2, 3, 4, 5, 6
```

## Minimum tests per model (schema.yml)

```yaml
models:
  - name: fct_ad_spend
    description: "Daily ad spend metrics by campaign. Source of truth for CPL."
    columns:
      - name: date
        tests: [not_null]
      - name: platform
        tests:
          - not_null
          - accepted_values:
              values: [facebook, google, tiktok, zalo]
      - name: office
        tests:
          - accepted_values:
              values: [HCM, HN, DN, UNKNOWN]
      - name: spend
        tests: [not_null]
    tests:
      - unique:
          column_name: "date || '_' || platform || '_' || campaign_id || '_' || coalesce(ad_set_id, 'null')"
      - dbt_utils.expression_is_true:
          expression: "spend >= 0"
      - dbt_utils.expression_is_true:
          expression: "leads >= 0"
      - dbt_utils.expression_is_true:
          expression: "clicks <= impressions or impressions = 0"
```

## After writing every model — mandatory sequence

```bash
dbt compile --select [model_name]    # 1. SQL valid?
dbt run --select [model_name]        # 2. Runs OK?
dbt test --select [model_name]       # 3. Tests pass?
```

**Never skip step 3.**

## Read examples before writing

- `examples/stg_example.sql` — staging pattern
- `examples/fct_example.sql` — fact/incremental pattern
- `examples/dim_example.sql` — dimension with SCD2
