import pandas as pd
import numpy as np
from faker import Faker
import random
from datetime import datetime, timedelta
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

fake = Faker()

def generate_data(num_records=1000):
    print(f"Generating {num_records} simulated M-Pesa transactions...")
    
    counties = ['Nairobi', 'Mombasa', 'Kiambu', 'Nakuru', 'Uasin Gishu', 'Kisumu', 'Kajiado']
    channels = ['PayBill', 'BuyGoods', 'SendMoney', 'Withdrawal']
    
    data = []
    start_date = datetime.now() - timedelta(days=30)
    
    for i in range(num_records):
        # Base transaction
        is_fraud = random.choices([0, 1], weights=[0.98, 0.02])[0]
        amount = random.uniform(10, 50000)
        
        # Injection of fraud patterns
        if is_fraud:
            pattern = random.choice(['high_amount', 'unusual_hour', 'velocity'])
            if pattern == 'high_amount':
                amount = random.uniform(100000, 250000)
            elif pattern == 'unusual_hour':
                # Night transactions
                ts = start_date + timedelta(days=random.randint(0, 30), hours=random.randint(1, 4))
            else:
                amount = random.uniform(10, 500) # Smurfing
        
        ts = start_date + timedelta(days=random.randint(0, 30), 
                                     hours=random.randint(0, 23), 
                                     minutes=random.randint(0, 59))
        
        data.append({
            'txn_id': fake.uuid4(),
            'user_id': fake.msisdn()[:10],
            'amount': round(amount, 2),
            'channel': random.choice(channels),
            'county': random.choice(counties),
            'txn_timestamp': ts,
            'is_fraud_label': is_fraud
        })
        
    return pd.DataFrame(data)

def ingest_to_db(df):
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5439')
    db_name = os.getenv('DB_NAME', 'mpesa_warehouse')
    db_user = os.getenv('DB_USER', 'mpesa_admin')
    db_pass = os.getenv('DB_PASSWORD', 'mpesa_password')
    
    engine = create_engine(f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}')
    
    print("Ingesting to PostgreSQL...")
    df.to_sql('raw_fraud_transactions', engine, if_exists='replace', index=False)
    print("✅ Ingestion complete.")

if __name__ == "__main__":
    df = generate_data(2000)
    ingest_to_db(df)
    # Save a local copy for dbt seeds or portability
    os.makedirs('data', exist_ok=True)
    df.to_csv('data/raw_transactions.csv', index=False)
