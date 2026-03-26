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
    line_records = day_df[day_df[mode_col].str.contains("line", case=False, na=False)]
    battery_records = day_df[day_df[mode_col].str.contains("battery", case=False, na=False)]
    
    # Calculate time in hours (assuming each record is ~1 minute based on typical inverter logs)
    line_time_hours = len(line_records) / 60  # Convert to hours
    battery_time_hours = len(battery_records) / 60
    
    st.subheader("⚡ Inverter Operation Mode Time Calculation (Kia kar raha hai)")
    
    # Show as bar chart
    mode_data = pd.DataFrame({
        'Mode': ['Grid/Mains (Line)', 'Battery (B)'],
        'Hours': [line_time_hours, battery_time_hours],
        'Records': [len(line_records), len(battery_records)]
    })
    fig_mode = px.bar(mode_data, x='Mode', y='Hours', title="Total Time in Each Mode", color='Mode',
                      color_discrete_map={'Grid/Mains (Line)': '#FFD700', 'Battery (B)': '#00CC96'})
    fig_mode.update_layout(yaxis_title="Hours")
    st.plotly_chart(fig_mode, use_container_width=True)
    
    # Also show as metrics
    col1, col2 = st.columns(2)
    col1.metric("🔌 Grid/Mains (Line) Time", f"{round(line_time_hours, 2)} hours")
    col2.metric("🔋 Battery Mode Time", f"{round(battery_time_hours, 2)} hours")

    # Battery Full (near 29V)
    full_battery = day_df[(day_df[voltage_col] >= 28.5)]
    st.subheader("🔋 Battery Status (Kitna charge hai?)")
    col1, col2 = st.columns(2)
    col1.metric("Full Battery (≈100%)", f"{len(full_battery)} records - Voltage ≥ 28.5V")
    
    # Low battery indicator
    low_battery = day_df[(day_df[voltage_col] < 24.0)]
    col2.metric("Low Battery (≈0-20%)", f"{len(low_battery)} records - Voltage < 24V")

    # Performance Score (simple logic)
    line_mode_time = len(line_records)
    battery_mode_time = len(battery_records)
    
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

    # Graphs for all parameters (per row, clickable)
    st.header("📈 All Parameters Graphs (Click points for details)")
    
    # Find all numeric columns
    numeric_cols = day_df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Remove helper columns
    numeric_cols = [c for c in numeric_cols if c not in ['hour']]
    
    # Key parameters to show
    key_params = [
        'battery_voltage', 'voltage', 'inner_temperature', 'temperature',
        'battery_charging_power', 'charging_power', 'battery_discharging_power', 'discharging_power',
        'grid_power_input_active_total', 'grid_power', 'solar_current_input_1', 'solar_current',
        'pv_input_voltage_1', 'pv_voltage'
    ]
    
    # Filter columns that match our key parameters
    display_cols = []
    for col in numeric_cols:
        col_lower = col.lower()
        if any(p in col_lower for p in key_params):
            display_cols.append(col)
    
    # If no key params found, show all numeric columns
    if not display_cols:
        display_cols = numeric_cols[:10]  # Show first 10 columns
    
    for col in display_cols:
        # Create interactive line chart for each parameter
        fig_param = px.line(day_df, x=datetime_col, y=col, 
                           title=f"{col.replace('_', ' ').title()}",
                           markers=True)
        fig_param.update_traces(mode="lines+markers")
        fig_param.update_layout(clickmode='event+select')
        st.plotly_chart(fig_param, use_container_width=True)

    # Raw Data
    with st.expander("View Raw Data"):
        st.dataframe(day_df)

else:
    st.info("Please upload an Excel file to begin analysis.")
