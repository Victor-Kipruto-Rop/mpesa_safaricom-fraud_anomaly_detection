import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import os

def generate_mpesa_fraud_data(num_samples=10000, output_dir="MPESA_Safaricom(pipeline)/Fraud_Anomaly_Detection/data"):
    os.makedirs(output_dir, exist_ok=True)
    
    # Feature parameters
    txn_types = ["C2B", "B2C", "B2B", "P2P"]
    risk_levels = ["Low", "Medium", "High"]
    
    data = []
    start_time = datetime.now() - timedelta(days=30)
    
    for i in range(num_samples):
        # Base transaction characteristics
        sender_id = f"2547{random.randint(10, 99)}{random.randint(100, 999)}{random.randint(100, 999)}"
        receiver_id = f"2547{random.randint(10, 99)}{random.randint(100, 999)}{random.randint(100, 999)}"
        amount = np.random.exponential(2500)
        txn_type = random.choice(txn_types)
        timestamp = start_time + timedelta(seconds=random.randint(0, 30*24*3600))
        
        # Fraud Indicators (Synthetic Features)
        velocity_60s = random.randint(1, 3) # Transactions in last minute
        sim_swap_days = random.randint(1, 365) # Days since last SIM swap
        is_night_txn = 1 if (timestamp.hour < 5 or timestamp.hour > 22) else 0
        is_fraud = 0
        
        # Inject Fraud Patterns
        # Pattern 1: Velocity Spike (Smurfing/Structuring)
        if random.random() < 0.02:
            velocity_60s = random.randint(8, 15)
            amount = random.randint(50, 500) # Small amounts in rapid succession
            is_fraud = 1
            
        # Pattern 2: High value after recent SIM swap
        if random.random() < 0.01:
            sim_swap_days = random.randint(0, 2)
            amount = random.randint(50000, 150000)
            is_fraud = 1
            
        # Pattern 3: Unusual night transfers
        if is_night_txn and random.random() < 0.05 and amount > 70000:
            is_fraud = 1

        data.append({
            "txn_id": f"TXN_{1000000 + i}",
            "timestamp": timestamp,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "amount": round(amount, 2),
            "txn_type": txn_type,
            "velocity_60s": velocity_60s,
            "sim_swap_days": sim_swap_days,
            "is_night_txn": is_night_txn,
            "is_fraud": is_fraud
        })

    df = pd.DataFrame(data)
    df.to_csv(f"{output_dir}/mpesa_fraud_training.csv", index=False)
    print(f"Generated {len(df)} transactions for Fraud detection in {output_dir}")

if __name__ == "__main__":
    generate_mpesa_fraud_data()
