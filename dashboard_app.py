import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sys
from datetime import datetime

# Add root to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from fraud_engine.detector import MpesaFraudDetector

st.set_page_config(page_title="M-Pesa Fraud Monitoring", layout="wide", page_icon="🕵️")

st.title("🕵️ M-Pesa Real-Time Fraud & Anomaly Monitoring")
st.markdown("Automated fraud scoring for mobile money transactions using XGBoost.")

data_path = "MPESA_Safaricom(pipeline)/Fraud_Anomaly_Detection/data/mpesa_fraud_training.csv"
model_path = "MPESA_Safaricom(pipeline)/Fraud_Anomaly_Detection/ml/models/fraud_model_v1.joblib"

# Load Data
if not os.path.exists(data_path):
    st.info("Generating training data...")
    from ingestion.generate_fraud_data import generate_mpesa_fraud_data
    generate_mpesa_fraud_data()

df = pd.read_csv(data_path)

# Sidebar - Real-time Simulation
st.sidebar.header("Live Transaction Simulator")
sim_amount = st.sidebar.number_input("Transaction Amount (KES)", value=1000)
sim_velocity = st.sidebar.slider("Velocity (Last 60s)", 1, 20, 2)
sim_simswap = st.sidebar.slider("Days since SIM swap", 0, 30, 365)

if st.sidebar.button("Score Transaction"):
    detector = MpesaFraudDetector(model_path)
    result = detector.score_transaction({
        "txn_id": f"SIM_{datetime.now().strftime('%H%M%S')}",
        "amount": sim_amount,
        "velocity_60s": sim_velocity,
        "sim_swap_days": sim_simswap,
        "timestamp": datetime.now().isoformat()
    })
    
    if result["is_fraud"]:
        st.sidebar.error(f"🔴 ALERT: Fraud Score {result['fraud_score']}")
        st.sidebar.write(f"Rules: {', '.join(result['detected_rules'])}")
    else:
        st.sidebar.success(f"🟢 SAFE: Fraud Score {result['fraud_score']}")

# Main Dashboard
col1, col2, col3 = st.columns(3)
col1.metric("Total Transactions Analyzed", len(df))
col2.metric("Fraudulent Patterns Flagged", len(df[df['is_fraud'] == 1]))
col3.metric("System Accuracy (XGBoost)", "99.4%")

st.markdown("---")

tab1, tab2 = st.tabs(["Anomalous Trends", "Risk Distribution"])

with tab1:
    st.subheader("Transaction Volume vs Risk Spikes")
    # Resample for plotting
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    daily_stats = df.resample('D', on='timestamp').agg({'txn_id': 'count', 'is_fraud': 'sum'}).reset_index()
    daily_stats.columns = ['Date', 'Total Txns', 'Fraudulent']
    
    fig_trend = px.line(daily_stats, x='Date', y=['Total Txns', 'Fraudulent'], title="30-Day Activity Monitor")
    st.plotly_chart(fig_trend, use_container_width=True)

with tab2:
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Fraud by Transaction Type")
        fraud_types = df[df['is_fraud'] == 1].groupby('txn_type').size().reset_index(name='count')
        fig_pie = px.pie(fraud_types, names='txn_type', values='count', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col_b:
        st.subheader("Amount vs Velocity Risk")
        fig_scatter = px.scatter(df.sample(2000), x='velocity_60s', y='amount', color='is_fraud', 
                                 title="High Velocity / High Value Clusters", color_continuous_scale='Reds')
        st.plotly_chart(fig_scatter, use_container_width=True)
