with stg as (
    select * from {{ ref('stg_transactions') }}
),
feature_engineering as (
    select
        *,
        extract(hour from transaction_at) as txn_hour,
        count(*) over (partition by user_id, date_trunc('day', transaction_at)) as daily_user_txn_count,
        avg(amount_kes) over (partition by user_id) as user_avg_amount,
        stddev(amount_kes) over (partition by user_id) as user_std_amount
    from stg
),
z_score_calc as (
    select
        *,
        (amount_kes - user_avg_amount) / nullif(user_std_amount, 0) as amount_z_score
    from feature_engineering
)
select * from z_score_calc
