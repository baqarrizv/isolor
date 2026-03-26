import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Inverter Analytics Dashboard", layout="wide")

st.title("🔋 Inverter & Battery Analytics Dashboard")
st.markdown("Upload your inverter Excel file and get detailed hourly & daily insights.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Normalize column names
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]

    # Try to detect columns
    datetime_col = [col for col in df.columns if "time" in col or "date" in col][0]
    load_col = [col for col in df.columns if "load" in col][0]
    voltage_col = [col for col in df.columns if "volt" in col][0]
    mode_col = [col for col in df.columns if "mode" in col or "status" in col][0]

    df[datetime_col] = pd.to_datetime(df[datetime_col])

    df["date"] = df[datetime_col].dt.date
    df["hour"] = df[datetime_col].dt.hour

    st.success("File Loaded Successfully ✅")

    # Sidebar filters
    selected_date = st.sidebar.selectbox("Select Date", sorted(df["date"].unique()))

    day_df = df[df["date"] == selected_date]

    st.header(f"📅 Analysis for {selected_date}")

    # Hourly Load
    hourly_load = day_df.groupby("hour")[load_col].mean().reset_index()

    fig_load = px.line(hourly_load, x="hour", y=load_col, markers=True, title="Hourly Load Output")
    st.plotly_chart(fig_load, use_container_width=True)

    # Line Mode vs Battery Mode
    line_mode_time = len(day_df[day_df[mode_col].str.contains("line", case=False, na=False)])
    battery_mode_time = len(day_df[day_df[mode_col].str.contains("battery", case=False, na=False)])

    st.subheader("⚡ Mode Usage")
    col1, col2 = st.columns(2)
    col1.metric("Line Mode Duration", f"{line_mode_time} records")
    col2.metric("Battery Mode Duration", f"{battery_mode_time} records")

    # Battery Full (near 29V)
    full_battery = day_df[(day_df[voltage_col] >= 28.5)]
    st.subheader("🔋 Battery Full (≈100%)")
    st.metric("Time at Full Charge", f"{len(full_battery)} records")

    # Performance Score (simple logic)
    performance_score = (
        (len(full_battery) / len(day_df)) * 40 +
        (line_mode_time / len(day_df)) * 30 +
        (1 - (battery_mode_time / len(day_df))) * 30
    )

    st.subheader("📊 Overall Performance Score")
    st.progress(int(performance_score))
    st.write(f"Score: {round(performance_score,2)} / 100")

    # Voltage Graph
    fig_voltage = px.line(day_df, x=datetime_col, y=voltage_col, title="Battery Voltage Trend")
    st.plotly_chart(fig_voltage, use_container_width=True)

    # Raw Data
    with st.expander("View Raw Data"):
        st.dataframe(day_df)

else:
    st.info("Please upload an Excel file to begin analysis.")
