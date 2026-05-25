import streamlit as st
import pandas as pd
import plotly.express as px
import os
from sqlalchemy import create_engine

st.set_page_config(page_title="M-Pesa Fraud Insights", layout="wide", page_icon="🛡️")

def get_engine():
    db_host = os.getenv('DB_HOST', 'localhost')
    db_name = os.getenv('DB_NAME', 'mpesa_warehouse')
    db_user = os.getenv('DB_USER', 'mpesa_admin')
    db_pass = os.getenv('DB_PASSWORD', 'mpesa_password')
    db_port = '5432' if db_host == 'postgres-mpesa' else '5439'
    return create_engine(f'postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}')

@st.cache_data(ttl=60)
def load_data(query):
    try:
        engine = get_engine()
        return pd.read_sql(query, engine)
    except:
        # Fallback to local csv if DB is down
        return pd.read_csv("data/raw_transactions.csv") if os.path.exists("data/raw_transactions.csv") else pd.DataFrame()

st.title("🛡️ M-Pesa Fraud Anomaly Detection")
st.sidebar.info("System utilizing Isolation Forest ML & dbt Transformation Layer")

# Metrics
df_county = load_data("SELECT * FROM fraud_summary_by_county")
if not df_county.empty:
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Fraud Rate", f"{df_county['fraud_rate'].mean():.2f}%")
    c2.metric("Most Flagged County", df_county.sort_values('fraud_count', ascending=False)['county'].iloc[0])
    c3.metric("Total Fraud Volume", f"KES {df_county['fraud_volume'].sum()/1e3:.1f}K")

st.markdown("---")

# Visuals
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("📍 Fraud Rate by County")
    fig = px.bar(df_county, x='county', y='fraud_rate', color='fraud_rate', color_continuous_scale='OrRd')
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.subheader("🕒 Fraud Concentration (Time of Day)")
    df_velocity = load_data("SELECT * FROM fraud_velocity_metrics")
    if not df_velocity.empty:
        fig_heat = px.density_heatmap(df_velocity, x='txn_hour', y='channel', z='fraud_count', color_continuous_scale='Purples')
        st.plotly_chart(fig_heat, use_container_width=True)

st.subheader("🔍 Individual Anomalies (ML Scored)")
df_flagged = load_data("SELECT * FROM int_flagged_transactions WHERE is_fraud_label = 1 LIMIT 10")
st.dataframe(df_flagged, use_container_width=True)
