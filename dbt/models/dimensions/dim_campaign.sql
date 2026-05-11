-- models/dimensions/dim_campaign.sql
-- Parse campaign metadata from 3-level naming convention:
--   Campaign:  {PLATFORM}_{TRUONG}_{YEARQ}_{OBJECTIVE}_[...]
--   Ad Set:    {OFFICE}_{AUDIENCE}_[...]
--   Ad:        {ASSET}_[...]

{{ config(
    materialized='table',
    schema='dw'
) }}

with source as (

    select distinct
        campaign_id,
        campaign_name,
        ad_set_id,
        ad_set_name,
        ad_id,
        ad_name
    from {{ ref('stg_facebook_ads') }}

),

parsed as (

    select
        campaign_id,
        campaign_name,
        ad_set_id,
        ad_set_name,
        ad_id,
        ad_name,

        -- Campaign level (4 required fields)
        split_part(campaign_name, '_', 1)           as platform,
        split_part(campaign_name, '_', 2)           as truong,
        split_part(campaign_name, '_', 3)           as yearq,
        split_part(campaign_name, '_', 4)           as objective,

        -- Ad Set level (2 required fields)
        split_part(ad_set_name, '_', 1)             as office,
        split_part(ad_set_name, '_', 2)             as audience,

        -- Ad level (1 required field)
        split_part(ad_name, '_', 1)                 as asset,

        now()                                       as updated_at

    from source

),

validated as (

    select
        *,
        -- Flag invalid values for monitoring
        office not in ('HCM', 'HN', 'DN', 'ALL', 'HCMTinh', 'HNTinh', 'DNTinh') as is_office_invalid,
        objective not in ('Lead', 'Conv', 'View', 'Traffic', 'Mix')               as is_objective_invalid
    from parsed

)

select * from validated
