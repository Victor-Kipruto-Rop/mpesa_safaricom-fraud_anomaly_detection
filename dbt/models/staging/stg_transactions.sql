with source as (
    select * from {{ source('mpesa_raw', 'raw_transactions') }}
),
renamed as (
    select
        transaction_id,
        sender_id,
        receiver_id,
        amount as amount_kes,
        transaction_type,
        county,
        timestamp as transaction_timestamp,
        case when is_fraud = 1 then true else false end as is_fraud_flag,
        ingested_at
    from source
)
select * from renamed
