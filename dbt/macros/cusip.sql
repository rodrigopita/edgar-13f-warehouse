{#-
  The CUSIP rules, named once. Characters are classified by ascii() and
  substr() and never by a pattern, so the same SQL runs in DuckDB and in
  Snowflake. A position is 1-based.
-#}

{#-
  The value of one character as the check digit counts it: 0 to 9 for the
  digits, 10 to 35 for A to Z, 36 for *, 37 for @, 38 for #. Null for any
  other character, a lower-case letter and a hyphen among them.
-#}
{% macro cusip_character_value(cusip, position) -%}
    case
        when ascii(substr({{ cusip }}, {{ position }}, 1)) between 48 and 57
            then ascii(substr({{ cusip }}, {{ position }}, 1)) - 48
        when ascii(substr({{ cusip }}, {{ position }}, 1)) between 65 and 90
            then ascii(substr({{ cusip }}, {{ position }}, 1)) - 55
        when ascii(substr({{ cusip }}, {{ position }}, 1)) = 42 then 36
        when ascii(substr({{ cusip }}, {{ position }}, 1)) = 64 then 37
        when ascii(substr({{ cusip }}, {{ position }}, 1)) = 35 then 38
    end
{%- endmacro %}

{#-
  Nine characters: the first eight a digit, an upper-case letter or one of
  * @ #, the ninth a digit.
-#}
{% macro cusip_is_well_formed(cusip) -%}
    length({{ cusip }}) = 9
    {%- for position in range(1, 9) %}
    and {{ cusip_character_value(cusip, position) }} is not null
    {%- endfor %}
    and ascii(substr({{ cusip }}, 9, 1)) between 48 and 57
{%- endmacro %}

{#-
  The digits of a character value times a multiplier, summed: v * m div 10
  + v * m mod 10. The multiplier is 1 at an odd position and 2 at an even
  one, and the sum applies to both, since a letter is a two-digit value.
  Floor and cast keep the division whole in both engines.
-#}
{% macro cusip_digit_sum(value, multiplier) -%}
    cast(floor({{ multiplier }} * {{ value }} / 10) as integer) + mod({{ multiplier }} * {{ value }}, 10)
{%- endmacro %}
