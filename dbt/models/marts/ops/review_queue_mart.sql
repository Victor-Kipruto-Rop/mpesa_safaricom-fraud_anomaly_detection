{{
  config(
    materialized='table',
    description='Review queue analytics for fraud analysts and ops',
    tags=['marts', 'ops']
  )
}}

-- Analytics mart for the fraud review queue
-- Tracks pending reviews, analyst workload, aging, and SLA

SELECT
    alert_id,
    transaction_id,
    detected_timestamp,
    ingestion_timestamp,
    
    -- Alert details
    risk_score,
    severity,
    detected_type,
    institution,
    
    -- Queue status
    CASE
        WHEN analyst_confirmed_label IS NULL THEN 'PENDING'
        ELSE 'RESOLVED'
    END AS queue_status,
    
    -- Analyst assignment (null if pending)
    analyst_id,
    
    -- Aging metrics
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - ingestion_timestamp)) / 60 AS queue_age_minutes,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - ingestion_timestamp)) / 3600 AS queue_age_hours,
    
    -- Review SLA tracking (target: 24 hours to review)
    CASE
        WHEN analyst_confirmed_label IS NULL THEN
            CASE
                WHEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - ingestion_timestamp)) / 3600 > 24 THEN 'OVERDUE'
                WHEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - ingestion_timestamp)) / 3600 > 12 THEN 'WARNING'
                ELSE 'ONTIME'
            END
        ELSE 'RESOLVED'
    END AS sla_status,
    
    -- Review speed (for resolved items)
    CASE
        WHEN analyst_confirmed_label IS NOT NULL THEN
            EXTRACT(EPOCH FROM (review_timestamp - ingestion_timestamp)) / 3600
        ELSE NULL
    END AS review_speed_hours,
    
    -- Outcome (for resolved items)
    analyst_confirmed_label AS outcome,
    review_timestamp,
    notes,
    
    -- Fraud confirmation metrics
    CASE
        WHEN analyst_confirmed_label = 'FRAUD' THEN 1
        ELSE 0
    END AS is_confirmed_fraud,
    
    CASE
        WHEN analyst_confirmed_label = 'LEGITIMATE' THEN 1
        ELSE 0
    END AS is_confirmed_legitimate,
    
    -- Analyst efficiency score (if resolved, lower review_lag = higher efficiency)
    CASE
        WHEN analyst_confirmed_label IS NOT NULL THEN
            100 - LEAST(100, GREATEST(0, (review_lag_minutes - 30) / 10))
        ELSE NULL
    END AS analyst_efficiency_score,
    
    -- Audit
    CURRENT_TIMESTAMP AS dbt_load_timestamp
    
FROM {{ ref('fct_fraud_decisions') }}
ORDER BY 
    CASE WHEN queue_status = 'PENDING' THEN 0 ELSE 1 END,
    queue_age_minutes DESC
