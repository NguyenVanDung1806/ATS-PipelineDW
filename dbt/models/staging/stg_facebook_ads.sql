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
        coalesce(ad_id::text, 'unknown')            as ad_id,

        -- dimensions
        date::date                                  as date,
        'facebook'::text                            as platform,

        -- metrics — EC-01: floor at 0, never negative
        greatest(spend::numeric(12, 2), 0)          as spend,
        greatest(impressions::bigint, 0)            as impressions,
        greatest(clicks::bigint, 0)                 as clicks,
        greatest(coalesce(leads::int, 0), 0)        as leads,

        -- metadata
        _loaded_at::timestamptz                     as loaded_at

    from source

)

select * from renamed
