-- models/marts/fct_paid_ads_daily.sql
-- Ad-level paid ads fact for audit and future multi-platform normalization.

{{ config(
    materialized='incremental',
    unique_key=['date', 'platform', 'campaign_id', 'ad_set_id', 'ad_id'],
    on_schema_change='fail',
    indexes=[
        {'columns': ['date', 'platform'], 'type': 'btree'},
        {'columns': ['campaign_id', 'date'], 'type': 'btree'},
        {'columns': ['ad_id', 'date'], 'type': 'btree'},
    ]
) }}

with spend as (

    select * from {{ ref('stg_facebook_ads') }}

    {% if is_incremental() %}
    where date >= coalesce(
        (select max(date) - interval '7 days' from {{ this }}),
        '2000-01-01'::date
    )
    {% endif %}

),

aggregated as (

    select
        date,
        platform,
        campaign_id,
        campaign_name,
        ad_set_id,
        ad_set_name,
        ad_id,
        ad_name,

        case
            when split_part(ad_set_name, '_', 1) in ('HCM', 'HN', 'DN', 'ALL', 'HCMTinh', 'HNTinh', 'DNTinh')
            then split_part(ad_set_name, '_', 1)
            else 'UNKNOWN'
        end                                             as office,

        sum(spend)                                      as spend,
        sum(impressions)                                as impressions,
        sum(reach)                                      as reach,
        sum(clicks)                                     as clicks,
        sum(link_clicks)                                as link_clicks,
        sum(website_leads)                              as website_leads,
        sum(native_form_leads)                          as native_form_leads,
        sum(platform_leads)                             as platform_leads,

        -- Backward-compatible legacy metric. Prefer split lead columns for new work.
        sum(leads)                                      as legacy_leads,

        max(action_attribution_windows)                 as action_attribution_windows,
        max(action_report_time)                         as action_report_time,
        max(report_timezone)                            as report_timezone,

        case
            when sum(platform_leads) > 0
            then round(sum(spend) / sum(platform_leads)::numeric, 2)
            else null
        end                                             as cpl_platform,

        case
            when sum(impressions) > 0
            then round(sum(link_clicks)::numeric / sum(impressions) * 100, 4)
            else null
        end                                             as link_ctr_pct,

        now()                                           as updated_at

    from spend
    group by 1, 2, 3, 4, 5, 6, 7, 8, 9

)

select * from aggregated
