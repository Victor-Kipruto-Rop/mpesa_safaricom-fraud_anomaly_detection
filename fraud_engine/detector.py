import joblib
import pandas as pd
import os
import json
from datetime import datetime

class MpesaFraudDetector:
    def __init__(self, model_path="MPESA_Safaricom(pipeline)/Fraud_Anomaly_Detection/ml/models/fraud_model_v1.joblib"):
        if os.path.exists(model_path):
            self.model = joblib.load(model_path)
            print(f"Loaded fraud model from {model_path}")
        else:
            self.model = None
            print("Warning: Fraud model not found. Scoring will be disabled.")

    def score_transaction(self, txn_data):
        """
        txn_data: dict with keys ['amount', 'velocity_60s', 'sim_swap_days', 'timestamp']
        """
        if self.model is None:
            return {"fraud_score": 0.0, "is_fraud": False, "status": "Model Missing"}
            
        # Feature Engineering
        timestamp = datetime.fromisoformat(txn_data['timestamp'])
        is_night_txn = 1 if (timestamp.hour < 5 or timestamp.hour > 22) else 0
        
        features = pd.DataFrame([{
            'amount': float(txn_data['amount']),
            'velocity_60s': int(txn_data['velocity_60s']),
            'sim_swap_days': int(txn_data['sim_swap_days']),
            'is_night_txn': is_night_txn
        }])
        
        # Predict probability
        prob = self.model.predict_proba(features)[0][1]
        is_fraud = prob > 0.7 # High threshold for blocking
        
        return {
            "txn_id": txn_data.get("txn_id"),
            "fraud_score": round(float(prob), 4),
            "is_fraud": bool(is_fraud),
            "timestamp": datetime.now().isoformat(),
            "detected_rules": self._explain_risk(txn_data, prob)
        }

    def _explain_risk(self, txn, prob):
        rules = []
        if txn['velocity_60s'] > 10: rules.append("Extreme Velocity Spike")
        if txn['sim_swap_days'] < 2 and txn['amount'] > 50000: rules.append("High Value Post-SIM Swap")
        if prob > 0.9: rules.append("Multiple Anomaly Correlation")
        return rules

if __name__ == "__main__":
    detector = MpesaFraudDetector()
    sample_txn = {
        "txn_id": "TEST_999",
        "amount": 120000,
        "velocity_60s": 12,
        "sim_swap_days": 1,
        "timestamp": datetime.now().isoformat()
    }
    print(json.dumps(detector.score_transaction(sample_txn), indent=2))
