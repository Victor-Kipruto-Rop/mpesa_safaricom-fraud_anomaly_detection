-- Macro: safe_divide
-- Safely divides two numbers, returning NULL if denominator is zero
-- Usage: {{ safe_divide(numerator, denominator) }}

{% macro safe_divide(numerator, denominator) %}
    CASE
        WHEN {{ denominator }} = 0 THEN NULL
        ELSE {{ numerator }}::NUMERIC / {{ denominator }}::NUMERIC
    END
{% endmacro %}
