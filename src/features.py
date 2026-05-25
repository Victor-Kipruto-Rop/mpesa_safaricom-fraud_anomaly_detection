import pandas as pd
import numpy as np

def calculate_z_score(amount, mean, std):
    if std == 0 or pd.isna(std):
        return 0
    return (amount - mean) / std

def extract_hour(timestamp):
    return pd.to_datetime(timestamp).hour

def is_unusual_hour(hour):
    # Unusual hours: 1 AM to 4 AM
    return 1 <= hour <= 4
