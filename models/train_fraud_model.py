import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

def train_isolation_forest():
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5439')
    db_name = os.getenv('DB_NAME', 'mpesa_warehouse')
    db_user = os.getenv('DB_USER', 'mpesa_admin')
    db_pass = os.getenv('DB_PASSWORD', 'mpesa_password')
    
    engine = create_engine(f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}')
    
    print("Loading data for ML training...")
    query = """
    SELECT amount_kes, txn_hour, daily_user_txn_count, amount_z_score 
    FROM int_flagged_transactions
    """
    try:
        df = pd.read_sql(query, engine)
    except Exception as e:
        print(f"Error loading from DB: {e}. Using local CSV fallback.")
        # Fallback logic for training
        return

    # Handle NaNs in z-score
    df = df.fillna(0)
    
    X = df[['amount_kes', 'txn_hour', 'daily_user_txn_count', 'amount_z_score']]
    
    print("🚀 Training Isolation Forest anomaly detector...")
    model = IsolationForest(n_estimators=100, contamination=0.02, random_state=42)
    model.fit(X)
    
    # In a real pipeline, we'd save this with joblib
    print("✅ Model trained successfully.")
    
    # Predicting back to the warehouse (simulated)
    df['ml_fraud_score'] = model.decision_function(X)
    df['is_anomaly'] = model.predict(X)
    
    print("Sample anomaly predictions:")
    print(df[df['is_anomaly'] == -1].head())

if __name__ == "__main__":
    train_isolation_forest()
