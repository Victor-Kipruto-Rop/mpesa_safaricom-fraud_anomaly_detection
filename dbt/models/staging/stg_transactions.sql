with source as (
    select * from {{ source('fraud_raw', 'raw_fraud_transactions') }}
),
renamed as (
    select
        txn_id as transaction_id,
        user_id,
        amount as amount_kes,
        channel,
        county,
        txn_timestamp as transaction_at,
        is_fraud_label
    from source
)
select * from renamed
