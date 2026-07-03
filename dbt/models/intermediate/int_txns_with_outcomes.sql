{{
  config(
    materialized='view',
    description='Intermediate: Transactions joined with analysis outcomes',
    tags=['intermediate']
  )
}}

-- Joins scored transactions with analyst-confirmed outcomes
-- Enables analysis of model performance vs analyst ground truth

SELECT
    fct.alert_id,
    fct.transaction_id,
    fct.institution,
    fct.detected_type,
    fct.risk_score,
    fct.severity,
    fct.rules_triggered,
    fct.detected_timestamp,
    fct.ingestion_timestamp,
    fct.alert_date,
    fct.alert_hour,
    
    -- Analyst outcome
    fct.analyst_confirmed_label,
    fct.analyst_id,
    fct.review_timestamp,
    fct.notes,
    fct.review_lag_minutes,
    
    -- Data quality flags
    fct.score_out_of_bounds,
    fct.future_timestamp_flag,
    
    -- Extracted fields
    stg.msisdn,
    stg.phone_number,
    CAST(stg.amount AS NUMERIC) AS transaction_amount,
    stg.transaction_time,
    stg.payment_method,
    stg.region,
    
    -- Decision mapping (from risk_score)
    CASE
        WHEN fct.risk_score >= 0.8 THEN 'BLOCK'
        WHEN fct.risk_score >= 0.5 THEN 'REVIEW'
        ELSE 'ALLOW'
    END AS decision,
    
    -- Confirmation indicator
    CASE
        WHEN fct.analyst_confirmed_label = 'FRAUD' THEN 1
        ELSE 0
    END AS is_confirmed_fraud,
    
    CASE
        WHEN fct.analyst_confirmed_label = 'LEGITIMATE' THEN 1
        ELSE 0
    END AS is_confirmed_legitimate,
    
    -- Performance metrics
    CASE
        WHEN decision = 'BLOCK' AND is_confirmed_fraud = 1 THEN 'TRUE_POSITIVE'
        WHEN decision = 'BLOCK' AND is_confirmed_legitimate = 1 THEN 'FALSE_POSITIVE'
        WHEN decision IN ('ALLOW', 'REVIEW') AND is_confirmed_fraud = 1 THEN 'FALSE_NEGATIVE'
        WHEN decision = 'ALLOW' AND is_confirmed_legitimate = 1 THEN 'TRUE_NEGATIVE'
        ELSE 'UNCONFIRMED'
    END AS outcome_classification,
    
    -- Audit
    CURRENT_TIMESTAMP AS dbt_load_timestamp
    
FROM {{ ref('fct_fraud_decisions') }} fct
LEFT JOIN {{ ref('stg_fraud_alerts') }} stg
    ON fct.transaction_id = stg.transaction_id
