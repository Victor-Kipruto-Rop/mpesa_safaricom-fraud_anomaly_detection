{{
  config(
    materialized='incremental',
    unique_id='alert_id',
    on_schema_change='fail',
    description='Fact table of fraud detection decisions with all dimensions',
    tags=['fraud', 'core_fact']
  )
}}

SELECT
    -- IDs
    a.alert_id,
    a.transaction_id,
    a.institution,
    
    -- Fraud signal
    a.detected_type,
    a.risk_score,
    a.severity,
    
    -- Rules that triggered
    a.rules_triggered,
    
    -- Timestamps
    a.detected_timestamp,
    a.ingestion_timestamp,
    EXTRACT(DATE FROM a.detected_timestamp) AS alert_date,
    EXTRACT(HOUR FROM a.detected_timestamp) AS alert_hour,
    
    -- Analyst outcome (joined after review)
    COALESCE(ro.confirmed_label, 'PENDING') AS analyst_confirmed_label,
    ro.analyst_id,
    ro.review_timestamp,
    ro.notes,
    
    -- SLA tracking
    CASE
        WHEN ro.review_timestamp IS NULL THEN NULL
        ELSE EXTRACT(EPOCH FROM (ro.review_timestamp - a.ingestion_timestamp)) / 60
    END AS review_lag_minutes,
    
    -- Data quality flags
    CASE 
        WHEN a.risk_score < 0 OR a.risk_score > 1 THEN TRUE 
        ELSE FALSE 
    END AS score_out_of_bounds,
    CASE 
        WHEN a.detected_timestamp > CURRENT_TIMESTAMP THEN TRUE 
        ELSE FALSE 
    END AS future_timestamp_flag,
    
    -- Audit
    CURRENT_TIMESTAMP AS dbt_load_timestamp
    
FROM {{ source('raw', 'fraud_alerts') }} a
LEFT JOIN {{ ref('stg_review_outcomes') }} ro
    ON a.alert_id = ro.alert_id

{% if execute %}
    {% if run_started_at %}
        WHERE a.ingestion_timestamp >= DATEADD(HOUR, -6, '{{ run_started_at }}')
    {% endif %}
{% endif %}
