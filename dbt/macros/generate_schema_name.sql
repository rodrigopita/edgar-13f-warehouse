{#-
  A model's custom schema is the schema it builds in. dbt's default appends
  the custom name to the target schema, so a model configured with
  schema: marts would build in CORE_MARTS; 07_dbt_identity.sql created
  CORE and MARTS, and TRANSFORMER can create in no other schema.
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
