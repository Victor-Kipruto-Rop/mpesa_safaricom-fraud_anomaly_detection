-- dbt test file: tests/mart/fct_fraud_decisions_tests.sql

-- Check uniqueness of alert_id (primary key)
{{ config(
    severity='error',
    description='Fact table alert_id should be unique'
) }}

SELECT alert_id, COUNT(*) AS count
FROM {{ ref('fct_fraud_decisions') }}
GROUP BY alert_id
HAVING COUNT(*) > 1
