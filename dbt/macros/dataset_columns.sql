{#-
  The data set conventions, named once. Every column arrives as text, an
  empty field as an empty string (the stage's NULL_IF is empty), a date as
  DD-MON-YYYY, a flag as Y or N or blank.
-#}
{% macro dataset_text(column) -%}
    nullif(trim({{ column }}), '')
{%- endmacro %}

{% macro dataset_date(column) -%}
    to_date({{ dataset_text(column) }}, 'DD-MON-YYYY')
{%- endmacro %}

{% macro dataset_number(column) -%}
    to_number({{ dataset_text(column) }})
{%- endmacro %}

{% macro dataset_flag(column) -%}
    case {{ dataset_text(column) }} when 'Y' then true when 'N' then false end
{%- endmacro %}

{#-
  The other-manager field of a holding, as filed: sequence numbers separated
  by commas, 0, NONE or blank. Every run of digits is a sequence number, as
  the XML parser reads it, so 0 is [0] and NONE and blank are [].
-#}
{% macro sequence_numbers(column) -%}
    coalesce(
        transform(regexp_substr_all({{ dataset_text(column) }}, '\\d+'), digits -> digits::number),
        array_construct()
    )
{%- endmacro %}
