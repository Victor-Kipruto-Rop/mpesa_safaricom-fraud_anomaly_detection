import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os

def train_fraud_model(data_path="MPESA_Safaricom(pipeline)/Fraud_Anomaly_Detection/data/mpesa_fraud_training.csv"):
    if not os.path.exists(data_path):
        print(f"Error: Training data not found at {data_path}")
        return

    df = pd.read_csv(data_path)
    
    # Feature engineering
    X = df[['amount', 'velocity_60s', 'sim_swap_days', 'is_night_txn']]
    y = df['is_fraud']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Train XGBoost
    model = XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        scale_pos_weight=10, # Handle class imbalance
        use_label_encoder=False,
        eval_metric='logloss'
    )
    
    print("Training M-Pesa Fraud Detection Model...")
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    print("\nModel Performance Metrics:")
    print(classification_report(y_test, y_pred))
    
    # Save model
    model_dir = "MPESA_Safaricom(pipeline)/Fraud_Anomaly_Detection/ml/models"
    os.makedirs(model_dir, exist_ok=True)
    model_path = f"{model_dir}/fraud_model_v1.joblib"
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_fraud_model()
