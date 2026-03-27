import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
from io import BytesIO

st.set_page_config(page_title="Inverter Analytics Dashboard", layout="wide")

st.title("🔋 Inverter Analytics Dashboard")
st.markdown("Upload your inverter Excel file or use a Google Sheet link and get detailed hourly & daily insights.")

# Option to choose data source - Default is Google Sheet
data_source = st.radio("Choose Data Source:", ["🔗 Google Sheet Link", "📁 Upload Excel File"], horizontal=True, index=0)

df = None

# Default Google Sheet URL (hardcoded)
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTy3qIf4XMXKwCzy4jhWksU5wm3KqYeqvFWVSusIehRxvn783TJwoBljQdkYiE5wETGaIsY_rSGl0P3/pub?output=xlsx"

if data_source == "🔗 Google Sheet Link":
    # Google Sheet option - use hardcoded URL by default
    use_custom_sheet = st.checkbox("Use different Google Sheet", value=False)
    
    if use_custom_sheet:
        sheet_url = st.text_input("🔗 Enter Custom Google Sheet URL (Published to Web)", 
                                  placeholder="https://docs.google.com/spreadsheets/d/e/.../pub?output=xlsx")
    else:
        sheet_url = DEFAULT_SHEET_URL
        st.info(f"📋 Using default Google Sheet")
    
    try:
        # Fetch the sheet
        response = requests.get(sheet_url)
        response.raise_for_status()
        
        # Read Excel from response
        df = pd.read_excel(BytesIO(response.content))
        st.success("Google Sheet Loaded Successfully ✅")
        
    except Exception as e:
        st.error(f"⚠️ Error loading Google Sheet: {str(e)}")
        st.info("Make sure the sheet is published to web and you have the correct URL.")
else:
    # Upload Excel File option
    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)

# Rest of the code remains the same
if df is not None:
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

    # Hourly Load
    hourly_load = day_df.groupby("hour")[load_col].mean().reset_index()

    fig_load = px.line(hourly_load, x="hour", y=load_col, markers=True, title="Hourly Load Output")
    st.plotly_chart(fig_load, use_container_width=True)

    # Line Mode vs Battery Mode - Calculate actual time between rows
    day_df[mode_col] = day_df[mode_col].astype(str)
    
    # Sort by datetime to ensure proper calculation
    day_df = day_df.sort_values(datetime_col).reset_index(drop=True)
    
    # Calculate time differences between consecutive rows (in hours)
    day_df['time_diff'] = day_df[datetime_col].diff().dt.total_seconds() / 3600
    
    # Fill first row with a small value (assuming 1 minute interval)
    day_df['time_diff'] = day_df['time_diff'].fillna(1/60)
    
    # Calculate time in each mode based on actual time between rows
    line_records = day_df[day_df[mode_col].str.contains("L", case=False, na=False)]
    battery_records = day_df[day_df[mode_col].str.contains("B", case=False, na=False)]
    
    # Sum up actual time spent in each mode
    line_time_hours = line_records['time_diff'].sum() if len(line_records) > 0 else 0
    battery_time_hours = battery_records['time_diff'].sum() if len(battery_records) > 0 else 0
    
    st.subheader("⚡ Inverter Operation Mode Time Calculation")
    
    # Show as bar chart
    mode_data = pd.DataFrame({
        'Mode': ['Grid (L)', 'Battery (B)'],
        'Hours': [line_time_hours, battery_time_hours],
        'Records': [len(line_records), len(battery_records)]
    })
    fig_mode = px.bar(mode_data, x='Mode', y='Hours', title="Total Time in Each Mode (Actual Time Between Rows)", color='Mode',
                      color_discrete_map={'Grid (L)': '#FFD700', 'Battery (B)': '#00CC96'})
    fig_mode.update_layout(yaxis_title="Hours")
    st.plotly_chart(fig_mode, use_container_width=True)
    
    # Also show as metrics
    col1, col2 = st.columns(2)
    col1.metric("🔌 Grid (L) Time", f"{round(line_time_hours, 2)} hours")
    col2.metric("🔋 Battery Mode Time", f"{round(battery_time_hours, 2)} hours")
    
    # Show mode distribution over time as a chart (per row) with start/end times
    st.write("📊 Mode Timeline (Har Row ki value)")
    day_df['mode_numeric'] = day_df[mode_col].apply(lambda x: 1 if 'L' in str(x).upper() else 0 if 'B' in str(x).upper() else 0.5)
    
    # Add time display column for hover
    day_df['Time'] = day_df[datetime_col].dt.strftime('%H:%M:%S')
    
    fig_timeline = px.scatter(day_df, x=datetime_col, y='mode_numeric', color=mode_col, 
                               title="Mode Timeline per Row (Click points for details)", 
                               color_discrete_map={'L': '#FFD700', 'B': '#00CC96'},
                               hover_data={'mode_numeric': False, 'Time': True, datetime_col: False})
    fig_timeline.update_layout(yaxis_title="Mode", yaxis=dict(tickvals=[0, 1], ticktext=['Battery (B)', 'Grid (L)']))
    fig_timeline.update_traces(marker=dict(size=10))
    st.plotly_chart(fig_timeline, use_container_width=True)
    

    # Battery Full (near 29V)
    full_battery = day_df[(day_df[voltage_col] >= 28.5)]
    st.subheader("🔋 Battery Status")
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

    st.subheader("📊 Inverter Performance")
    st.progress(int(performance_score))
    st.write(f"**Score: {round(performance_score,2)} / 100**")
    
    if performance_score >= 70:
        st.success("✅ Great performance! Inverter is working efficiently.")
    elif performance_score >= 40:
        st.warning("⚠️ Average performance. Check battery charging.")
    else:
        st.error("❌ Poor performance. Needs attention!")

    # Find numeric columns - needed for both voltage and power charts
    numeric_cols = day_df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [c for c in numeric_cols if c not in ['hour', 'time_diff', 'mode_numeric', 'mode_change', 'period_id']]
    
    # Key parameters to show in hover
    key_params = [
        'ac_output_active_power_total', 'ac_output_load_r', 'ac_output_load_total',
        'pv_input_power_1', 'discharging_current', 'battery_voltage', 'voltage'
    ]
    
    # Filter columns
    display_cols = []
    for col in numeric_cols:
        col_lower = col.lower()
        if any(p in col_lower for p in key_params):
            display_cols.append(col)
    
    if not display_cols:
        display_cols = numeric_cols[:7]
    
    # Prepare sorted data
    day_df_sorted = day_df.sort_values(datetime_col).reset_index(drop=True).copy()
    
    # Voltage Graph with hover showing all parameters
    st.subheader("🔋 Battery Voltage Trend")
    
    # Create hover_data for voltage chart
    hover_data_voltage = {}
    for col in display_cols:
        if col != voltage_col:
            hover_data_voltage[col] = ':.2f'
    
    hover_data_voltage[datetime_col] = ':%H:%M:%S'
    hover_data_voltage[mode_col] = True
    
    # Create voltage chart
    fig_voltage = px.line(day_df_sorted, x=datetime_col, y=voltage_col,
                         title="Battery Voltage Trend - Hover to see all parameters",
                         markers=True,
                         hover_data=hover_data_voltage)
    
    fig_voltage.update_layout(
        hovermode='closest',
        hoverdistance=-1
    )
    
    st.plotly_chart(fig_voltage, use_container_width=True)

    # One main graph with AC Output Active Power Total - hover shows all values
    st.header("📊 AC Output Active Power Total - Hover for all values")
    
    # Main column is AC Output Active Power Total
    main_col = None
    for col in display_cols:
        if 'ac_output_active_power_total' in col.lower():
            main_col = col
            break
    if main_col is None:
        main_col = display_cols[0]
    
    # Create hover_data dict - shows all parameters on hover
    hover_data = {}
    for col in display_cols:
        if col != main_col:  # Skip main col as it's already shown
            hover_data[col] = ':.2f'  # Format to 2 decimal places
    
    # Also add time and mode to hover
    hover_data[datetime_col] = ':%H:%M:%S'
    hover_data[mode_col] = True
    
    # Create one main line chart with ALL parameters in hover
    fig_main = px.line(day_df_sorted, x=datetime_col, y=main_col,
                       title="AC Output Active Power Total - Hover to see all parameters",
                       markers=True,
                       hover_data=hover_data)
    
    # Update layout for unified hover mode
    fig_main.update_layout(
        hovermode='closest',
        hoverdistance=-1
    )
    
    st.plotly_chart(fig_main, use_container_width=True)
    
    # Raw Data
    with st.expander("View Raw Data"):
        st.dataframe(day_df)

else:
    st.info("Please upload an Excel file or enter a Google Sheet link to begin analysis.")
