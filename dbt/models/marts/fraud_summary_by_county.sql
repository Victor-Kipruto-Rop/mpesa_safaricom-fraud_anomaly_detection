with flagged as (
    select * from {{ ref('int_flagged_transactions') }}
),
summary as (
    select
        county,
        count(*) as total_txns,
        sum(case when is_fraud_label = 1 then 1 else 0 end) as fraud_count,
        sum(amount_kes) as total_volume,
        avg(amount_z_score) as avg_z_score
    from flagged
    group by 1
)
select 
    *,
    (fraud_count::float / nullif(total_txns, 0)) * 100 as fraud_rate
from summary
