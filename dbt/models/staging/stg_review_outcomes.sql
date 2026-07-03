{{
  config(
    materialized='view',
    description='Staging: Typed raw review outcomes',
    tags=['staging']
  )
}}

SELECT
    outcome_id,
    alert_id,
    confirmed_label,
    analyst_id,
    review_timestamp,
    notes,
    
    -- Type coercion & validation
    CAST(confirmed_label AS VARCHAR) AS confirmed_label_typed,
    CASE 
        WHEN confirmed_label NOT IN ('FRAUD', 'LEGITIMATE', 'SUSPICIOUS') 
        THEN TRUE ELSE FALSE 
    END AS invalid_label_flag,
    
    dbt_load_timestamp
    
FROM {{ source('raw', 'review_outcomes') }}
