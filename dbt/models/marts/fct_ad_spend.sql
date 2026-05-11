-- models/marts/fct_ad_spend.sql
-- FACT TABLE: additive metrics, UPSERT-safe, partitioned by month
-- Skills auto-loaded: dbt-conventions, sql-optimizer

{{ config(
    materialized='incremental',
    unique_key=['date', 'platform', 'campaign_id', 'ad_set_id'],
    on_schema_change='fail',
    indexes=[
        {'columns': ['date', 'platform'], 'type': 'btree'},
        {'columns': ['office', 'date'], 'type': 'btree'},
    ]
) }}

with spend as (

    select * from {{ ref('stg_facebook_ads') }}

    {% if is_incremental() %}
    -- EC-06: lookback 7 days; coalesce handles first-run empty table (max=NULL)
    where date >= coalesce(
        (select max(date) - interval '7 days' from {{ this }}),
        '2000-01-01'::date
    )
    {% endif %}

),

enriched as (

    select
        date,
        platform,
        campaign_id,
        campaign_name,
        ad_set_id,
        ad_set_name,

        -- EC-10: extract office from ad_set_name position 1
        -- Pattern: {OFFICE}_{AUDIENCE}_[...] → position 1
        -- Valid: HCM, HN, DN, ALL, HCMTinh, HNTinh, DNTinh
        case
            when split_part(ad_set_name, '_', 1) in ('HCM', 'HN', 'DN', 'ALL', 'HCMTinh', 'HNTinh', 'DNTinh')
            then split_part(ad_set_name, '_', 1)
            else 'UNKNOWN'
        end                                             as office,

        sum(spend)                                      as spend,
        sum(impressions)                                as impressions,
        sum(clicks)                                     as clicks,
        sum(leads)                                      as leads,

        -- Derived metrics (safe division — EC-01)
        case
            when sum(leads) > 0
            then round(sum(spend) / sum(leads)::numeric, 2)
            else null
        end                                             as cpl,

        case
            when sum(impressions) > 0
            then round(sum(clicks)::numeric / sum(impressions) * 100, 4)
            else null
        end                                             as ctr_pct,

        now()                                           as updated_at

    from spend
    group by 1, 2, 3, 4, 5, 6, 7

)

select * from enriched
