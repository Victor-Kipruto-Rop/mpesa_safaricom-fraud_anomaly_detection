{{
  config(
    materialized='table',
    description='Business impact analytics: fraud caught, false positives, revenue protection',
    tags=['marts', 'business']
  )
}}

-- Business impact mart for leadership reporting
-- Tracks fraud value caught vs missed, false positive costs, decision distributions

SELECT
    DATE(detected_timestamp) AS impact_date,
    EXTRACT(HOUR FROM detected_timestamp) AS impact_hour,
    
    -- Decision distribution (from risk score thresholds)
    COUNT(DISTINCT CASE WHEN risk_score >= 0.8 THEN alert_id END) AS block_count,
    COUNT(DISTINCT CASE WHEN risk_score BETWEEN 0.5 AND 0.8 THEN alert_id END) AS review_count,
    COUNT(DISTINCT CASE WHEN risk_score < 0.5 THEN alert_id END) AS allow_count,
    
    -- Fraud value metrics (in KES)
    COALESCE(SUM(
        CASE
            WHEN analyst_confirmed_label = 'FRAUD' 
            THEN 10000  -- Placeholder transaction value (would come from transaction table)
            ELSE 0
        END
    ), 0) AS fraud_value_caught_kes,
    
    COALESCE(SUM(
        CASE
            WHEN analyst_confirmed_label = 'FRAUD'
            AND risk_score < 0.8
            THEN 10000
            ELSE 0
        END
    ), 0) AS fraud_value_missed_kes,
    
    -- False positive cost (assumed cost per false positive = 500 KES for customer service)
    COALESCE(COUNT(DISTINCT CASE
        WHEN risk_score >= 0.8
        AND analyst_confirmed_label = 'LEGITIMATE'
        THEN alert_id
    END) * 500, 0) AS false_positive_cost_kes,
    
    -- True positive and false positive rates
    {{ safe_divide(
        'COUNT(DISTINCT CASE WHEN analyst_confirmed_label = \'FRAUD\' THEN alert_id END)',
        'COUNT(DISTINCT CASE WHEN analyst_confirmed_label IN (\'FRAUD\', \'LEGITIMATE\') THEN alert_id END)'
    ) }} AS fraud_confirmation_rate_pct,
    
    {{ safe_divide(
        'COUNT(DISTINCT CASE WHEN risk_score >= 0.8 AND analyst_confirmed_label IN (\'FRAUD\', \'LEGITIMATE\') THEN alert_id END)',
        'COUNT(DISTINCT CASE WHEN risk_score >= 0.8 THEN alert_id END)'
    ) }} AS block_accuracy_rate_pct,
    
    -- Customer impact
    COUNT(DISTINCT institution) AS institutions_impacted,
    COUNT(DISTINCT CASE WHEN risk_score >= 0.8 THEN institution END) AS institutions_blocked,
    
    -- Risk score metrics
    AVG(CASE WHEN analyst_confirmed_label = 'FRAUD' THEN risk_score END) AS avg_fraud_risk_score,
    AVG(CASE WHEN analyst_confirmed_label = 'LEGITIMATE' THEN risk_score END) AS avg_legitimate_risk_score,
    
    -- Check performance (which checks triggered)
    COUNT(DISTINCT CASE WHEN analyst_confirmed_label = 'FRAUD' THEN alert_id END) AS fraud_alerts_confirmed,
    
    -- Audit
    CURRENT_TIMESTAMP AS dbt_load_timestamp
    
FROM {{ ref('fct_fraud_decisions') }}

WHERE detected_timestamp >= CURRENT_DATE - INTERVAL '90 days'

GROUP BY 
    DATE(detected_timestamp),
    EXTRACT(HOUR FROM detected_timestamp)

ORDER BY impact_date DESC, impact_hour DESC
