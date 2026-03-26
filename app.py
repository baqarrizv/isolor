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

    # Try to detect columns with error handling
    try:
        datetime_col = [col for col in df.columns if "time" in col or "date" in col][0]
        load_col = [col for col in df.columns if "load" in col][0]
        voltage_col = [col for col in df.columns if "volt" in col][0]
        mode_col = [col for col in df.columns if "mode" in col or "status" in col][0]
    except IndexError:
        st.error("⚠️ Could not detect required columns. Please ensure your Excel file has columns containing: time/date, load, voltage, mode/status.")
        st.write("**Detected columns:**", df.columns.tolist())
        st.stop()

    df[datetime_col] = pd.to_datetime(df[datetime_col], errors='coerce')

    # Check for invalid datetime values
    if df[datetime_col].isna().all():
        st.error("⚠️ Could not parse datetime column. Please check your data format.")
        st.stop()

    df["date"] = df[datetime_col].dt.date
    df["hour"] = df[datetime_col].dt.hour

    st.success("File Loaded Successfully ✅")

    # Sidebar filters
    date_options = sorted(df["date"].unique(), reverse=True)
    if len(date_options) == 0:
        st.error("⚠️ No valid dates found in the data.")
        st.stop()
    
    selected_date = st.sidebar.selectbox("Select Date", date_options)

    day_df = df[df["date"] == selected_date]

    if len(day_df) == 0:
        st.warning("No data available for the selected date.")
        st.stop()

    st.header(f"📅 Analysis for {selected_date}")

    # Show all available parameters
    st.subheader("📋 Available Parameters in Data")
    all_cols = df.columns.tolist()
    st.write("**All columns in your data:**")
    for i, col in enumerate(all_cols):
        st.write(f"{i+1}. {col}")
    
    # Show unique values in mode column for inverter users
    st.subheader("⚙️ Inverter Mode Status")
    unique_modes = day_df[mode_col].unique()
    st.write(f"**Modes detected:** {list(unique_modes)}")

    # Hourly Load
    hourly_load = day_df.groupby("hour")[load_col].mean().reset_index()

    fig_load = px.line(hourly_load, x="hour", y=load_col, markers=True, title="Hourly Load Output")
    st.plotly_chart(fig_load, use_container_width=True)

    # Line Mode vs Battery Mode
    # Safely handle mode column
    day_df[mode_col] = day_df[mode_col].astype(str)
    line_mode_time = len(day_df[day_df[mode_col].str.contains("line", case=False, na=False)])
    battery_mode_time = len(day_df[day_df[mode_col].str.contains("battery", case=False, na=False)])

    st.subheader("⚡ Inverter Operation Mode (Kia kar raha hai)")
    col1, col2 = st.columns(2)
    col1.metric("🔌 Grid/Mains Mode (Line)", f"{line_mode_time} records - Power from grid")
    col2.metric("🔋 Battery Mode", f"{battery_mode_time} records - Power from battery")

    # Battery Full (near 29V)
    full_battery = day_df[(day_df[voltage_col] >= 28.5)]
    st.subheader("🔋 Battery Status (Kitna charge hai?)")
    col1, col2 = st.columns(2)
    col1.metric("Full Battery (≈100%)", f"{len(full_battery)} records - Voltage ≥ 28.5V")
    
    # Low battery indicator
    low_battery = day_df[(day_df[voltage_col] < 24.0)]
    col2.metric("Low Battery (≈0-20%)", f"{len(low_battery)} records - Voltage < 24V")

    # Performance Score (simple logic)
    performance_score = (
        (len(full_battery) / len(day_df)) * 40 +
        (line_mode_time / len(day_df)) * 30 +
        (1 - (battery_mode_time / len(day_df))) * 30
    )

    st.subheader("📊 Inverter Performance (Kitna behtareen kaam kar raha hai)")
    st.progress(int(performance_score))
    st.write(f"**Score: {round(performance_score,2)} / 100**")
    
    if performance_score >= 70:
        st.success("✅ Great performance! Inverter is working efficiently.")
    elif performance_score >= 40:
        st.warning("⚠️ Average performance. Check battery charging.")
    else:
        st.error("❌ Poor performance. Needs attention!")

    # Voltage Graph
    fig_voltage = px.line(day_df, x=datetime_col, y=voltage_col, title="Battery Voltage Trend")
    st.plotly_chart(fig_voltage, use_container_width=True)

    # Raw Data
    with st.expander("View Raw Data"):
        st.dataframe(day_df)

else:
    st.info("Please upload an Excel file to begin analysis.")
