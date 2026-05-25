-- models/staging/stg_facebook_ads.sql
-- STAGING RULE: rename + cast only. No joins. No business logic.
-- Skills auto-loaded when editing this file: dbt-conventions

with source as (

    select * from {{ source('raw', 'facebook_ads') }}

),

renamed as (

    select
        -- identifiers
        campaign_id::text                           as campaign_id,
        campaign_name::text                         as campaign_name,
        coalesce(ad_set_id::text, 'unknown')        as ad_set_id,
        coalesce(ad_set_name::text, 'unknown')      as ad_set_name,
        coalesce(ad_id::text, 'unknown')            as ad_id,
        coalesce(ad_name::text, 'unknown')          as ad_name,

        -- dimensions
        date::date                                  as date,
        'facebook'::text                            as platform,

        -- metrics — EC-01: floor at 0, never negative
        greatest(spend::numeric(12, 2), 0)          as spend,
        greatest(impressions::bigint, 0)            as impressions,
        greatest(coalesce(reach::bigint, 0), 0)     as reach,
        greatest(clicks::bigint, 0)                 as clicks,
        greatest(coalesce(link_clicks::bigint, 0), 0) as link_clicks,
        actions_json::jsonb                         as actions_json,
        greatest(coalesce(website_leads::int, 0), 0) as website_leads,
        greatest(coalesce(native_form_leads::int, 0), 0) as native_form_leads,
        greatest(coalesce(platform_leads::int, 0), 0) as platform_leads,
        greatest(coalesce(leads::int, 0), 0)        as leads,
        coalesce(action_attribution_windows::text, '1d_click') as action_attribution_windows,
        coalesce(action_report_time::text, 'conversion') as action_report_time,
        report_timezone::text                       as report_timezone,

        -- metadata
        loaded_at::timestamptz                      as loaded_at

    from source

)

select * from renamed
