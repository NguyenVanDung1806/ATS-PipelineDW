-- Override dbt's default schema concatenation behavior.
-- Default: {profile_schema}_{custom_schema} → e.g. raw_dw
-- This macro: use custom_schema directly → e.g. dw
-- If no custom schema defined, fall back to profile schema.

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
