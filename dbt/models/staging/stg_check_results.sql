{{
  config(
    materialized='view',
    description='Staging: Unpacked per-check trigger results from fraud alerts',
    tags=['staging']
  )
}}

-- Unpacks rules_triggered JSON array into individual check rows
-- Enables per-check analysis and drill-down

SELECT
    a.alert_id,
    a.transaction_id,
    a.detected_timestamp,
    
    -- Unnested check results (assuming rules_triggered is JSON array)
    check_name,
    check_triggered,
    check_score,
    
    -- Audit
    CURRENT_TIMESTAMP AS dbt_load_timestamp
    
FROM {{ source('raw', 'fraud_alerts') }} a
-- Cross join with unnested check results
-- Note: SQL dialect varies; adapt to PostgreSQL JSONB or Snowflake FLATTEN
CROSS JOIN LATERAL (
    SELECT
        jsonb_array_elements(a.rules_triggered)->>'check_name' AS check_name,
        (jsonb_array_elements(a.rules_triggered)->>'triggered')::BOOLEAN AS check_triggered,
        (jsonb_array_elements(a.rules_triggered)->>'score')::FLOAT AS check_score
) checks
