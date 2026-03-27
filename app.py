import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
import os
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
    
    # Check if local file exists and load it
    local_file = 'simplefile.xlsx'
    if os.path.exists(local_file):
        try:
            df = pd.read_excel(local_file)
            st.success(f"Loaded local file: {local_file} ✅")
        except Exception as e:
            st.warning(f"Could not load local file: {e}")
            if uploaded_file:
                df = pd.read_excel(uploaded_file)
    elif uploaded_file:
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
    
    # Option to view load as hourly average or row-wise
    load_view_mode = st.radio("Load View Mode:", ["Hourly Average", "Row-wise (Every Entry)"], horizontal=True, index=0)
    
    # Sort data by datetime for row-wise view
    day_df_sorted_load = day_df.sort_values(datetime_col).reset_index(drop=True)
    
    # Find work_mode column for hover display
    work_mode_col_load = None
    for col in day_df_sorted_load.columns:
        if 'work_mode' in col.lower():
            work_mode_col_load = col
            break
    
    # Get display_cols for hover (need to get numeric cols first)
    numeric_cols_for_load = day_df_sorted_load.select_dtypes(include=[np.number]).columns.tolist()
    
    # Key params for hover - include load_col
    key_params_load = [
        'ac_output_active_power_total',
        'ac_output_load_r',
        'ac_output_load_total',
        'pv_input_power_1',
        'discharging_current',
        'grid_power_input_active_total',
        'battery_voltage',
        load_col
    ]
    
    # Filter columns - also include load_col
    display_cols_load = []
    for col in numeric_cols_for_load:
        col_lower = col.lower()
        if col_lower in key_params_load:
            display_cols_load.append(col)
        if col == load_col and col not in display_cols_load:
            display_cols_load.append(col)
    
    if not display_cols_load:
        display_cols_load = numeric_cols_for_load[:7]
    
    # Custom labels - include load_col
    custom_labels_load = {
        'ac_output_active_power_total': 'AC Output Power (W)',
        'ac_output_load_r': 'Load R (%)',
        'ac_output_load_total': 'Load Total (%)',
        'pv_input_power_1': 'PV Input Power (W)',
        'discharging_current': 'Discharge (Amp)',
        'grid_power_input_active_total': 'Grid Power Input (W)',
        'battery_voltage': 'Battery (V)',
        load_col: 'Load Output %'
    }
    
    # Hourly Load
    if load_view_mode == "Hourly Average":
        hourly_load = day_df.groupby("hour")[load_col].mean().reset_index()
        fig_load = px.line(hourly_load, x="hour", y=load_col, markers=True, title="Hourly Load Output % Wise (Average)")
    else:
        # Row-wise view - show every data point sorted by time with hover
        row_load = day_df_sorted_load[[datetime_col, load_col]].copy()
        fig_load = px.line(day_df_sorted_load, x=datetime_col, y=load_col, markers=True, title="Load Output % Wise - Every Entry (Row-wise)")
        fig_load.update_layout(xaxis_title="Time", yaxis_title=f"Load %")
        
        # Build custom hover with key params for row-wise view
        load_hover = f"<b>Load %</b>: %{{y:.2f}}<br>"
        for i, col in enumerate(display_cols_load):
            friendly = custom_labels_load.get(col, col)
            load_hover += f"<b>{friendly}</b>: %{{customdata[{i}]}}<br>"
        
        if work_mode_col_load:
            load_hover += f"<b>Work Mode</b>: %{{customdata[{len(display_cols_load)}]}}<br>"
        load_hover += f"<b>Time</b>: %{{x}}"
        
        # Prepare customdata
        load_customdata = []
        for _, row in day_df_sorted_load.iterrows():
            row_data = []
            for col in display_cols_load:
                val = row[col] if pd.notna(row[col]) else 0
                row_data.append(f"{val:.2f}")
            if work_mode_col_load:
                row_data.append(str(row[work_mode_col_load]))
            load_customdata.append(tuple(row_data))
        
        fig_load.update_traces(hovertemplate=load_hover, customdata=load_customdata)
        fig_load.update_layout(hovermode='closest', hoverdistance=-1)
    
    st.plotly_chart(fig_load, use_container_width=True)
    
    # Find numeric columns - needed for both voltage and power charts
    numeric_cols = day_df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [c for c in numeric_cols if c not in ['hour', 'time_diff', 'mode_numeric', 'mode_change', 'period_id']]
    
    # Key parameters to show in hover - EXACT headers from Excel file
    key_params = [
        'ac_output_active_power_total',    # Main value at index 0
        'ac_output_load_r',
        'ac_output_load_total',
        'pv_input_power_1',
        'discharging_current',
        'grid_power_input_active_total',
        'work_mode',
        'battery_voltage',
        load_col  # Add Load %
    ]
    
    # Custom display names for hover - show friendly names instead of column names
    custom_labels = {
        'ac_output_active_power_total': 'AC Output Active Power Total (W)',
        'ac_output_load_r': 'AC Output Load R (%)',
        'ac_output_load_total': 'AC Output Load Total (%)',
        'pv_input_power_1': 'PV Input Power (W)',
        'discharging_current': 'Discharging (Amp)',
        'grid_power_input_active_total': 'Grid Power Input (W)',
        'work_mode': 'Work Mode',
        'battery_voltage': 'Battery Voltage (V)',
        load_col: 'Load Output %'
    }
    
    # Filter numeric columns - exact match with normalized names
    display_cols = []
    for col in numeric_cols:
        col_lower = col.lower()
        if col_lower in key_params:
            display_cols.append(col)
        # Also add load_col
        if col == load_col and col not in display_cols:
            display_cols.append(col)
    
    # Also check for work_mode in all columns (it's not numeric)
    work_mode_col = None
    for col in day_df.columns:
        if 'work_mode' in col.lower():
            work_mode_col = col
            break
    
    # If no exact matches, try partial match
    if not display_cols:
        for col in numeric_cols:
            col_lower = col.lower()
            if any(p.replace('_', '') in col_lower.replace('_', '') for p in key_params):
                display_cols.append(col)
    
    # If still no columns, use first 7
    if not display_cols:
        display_cols = numeric_cols[:7]
    
    # Prepare sorted data
    day_df_sorted = day_df.sort_values(datetime_col).reset_index(drop=True).copy()
    
    # Find work_mode column for hover display
    work_mode_col = None
    for col in day_df_sorted.columns:
        if 'work_mode' in col.lower():
            work_mode_col = col
            break
    
    # Grid Voltage Graph with hover showing all parameters
    st.subheader("📈 Grid Voltage Trend")
    
    # Create hover_data for voltage chart
    hover_data_voltage = {}
    for col in display_cols:
        if col != voltage_col:
            hover_data_voltage[col] = ':.2f'
    
    hover_data_voltage[datetime_col] = ':%H:%M:%S'
    
    # Create voltage chart
    fig_voltage = px.line(day_df_sorted, x=datetime_col, y=voltage_col,
                         title="Grid Voltage Trend",
                         markers=True,
                         hover_data=hover_data_voltage)
    
    # Build custom hover template with friendly names for voltage chart
    voltage_label = custom_labels.get(voltage_col, voltage_col)
    voltage_hover = f"<b>{voltage_label}</b>: %{{y:.2f}}<br>"
    
    other_voltage_cols = [col for col in display_cols if col != voltage_col]
    for i, col in enumerate(other_voltage_cols):
        friendly_name = custom_labels.get(col, col)
        voltage_hover += f"<b>{friendly_name}</b>: %{{customdata[{i}]}}<br>"
    
    # Add work_mode before Time (second to last)
    if work_mode_col:
        voltage_hover += f"<b>Work Mode</b>: %{{customdata[{len(other_voltage_cols)}]}}<br>"
    
    # Add time (last)
    voltage_hover += f"<b>Time</b>: %{{x}}"
    
    # Prepare customdata for voltage chart
    voltage_customdata = []
    for _, row in day_df_sorted.iterrows():
        row_data = []
        for col in other_voltage_cols:
            val = row[col] if pd.notna(row[col]) else 0
            row_data.append(f"{val:.2f}")
        # Add work_mode at the end if found
        if work_mode_col:
            row_data.append(str(row[work_mode_col]))
        voltage_customdata.append(tuple(row_data))
    
    fig_voltage.update_traces(
        hovertemplate=voltage_hover,
        customdata=voltage_customdata
    )
    
    fig_voltage.update_layout(
        hovermode='closest',
        hoverdistance=-1
    )
    
    st.plotly_chart(fig_voltage, use_container_width=True)
    
    # Separate Battery Voltage Graph
    st.subheader("🔋 Battery Voltage Trend")
    
    # Find battery_voltage column
    battery_col = None
    for col in day_df_sorted.columns:
        if 'battery_voltage' in col.lower():
            battery_col = col
            break
    
    if battery_col:
        # Reorder display_cols: Battery Voltage first, then others in same order as AC Output
        # Remove battery_col from display_cols if it exists
        other_params = [col for col in display_cols if col.lower() != 'battery_voltage']
        # Add battery_col at the beginning
        battery_display_cols = [battery_col] + other_params
        
        # Create hover_data dict
        battery_hover_data = {}
        for col in battery_display_cols:
            if col != battery_col:
                battery_hover_data[col] = ':.2f'
        battery_hover_data[datetime_col] = ':%H:%M:%S'
        
        # Create battery voltage chart
        fig_battery = px.line(day_df_sorted, x=datetime_col, y=battery_col,
                             title="Battery Voltage Trend",
                             markers=True,
                             hover_data=battery_hover_data)
        
        # Build custom hover with Battery Voltage first (same pattern as AC Output)
        battery_hover = f"<b>Battery Voltage (V)</b>: %{{y:.2f}}<br>"
        
        # Add other columns after battery voltage (excluding battery_col)
        other_battery_cols = [col for col in battery_display_cols if col != battery_col]
        for i, col in enumerate(other_battery_cols):
            friendly = custom_labels.get(col, col)
            battery_hover += f"<b>{friendly}</b>: %{{customdata[{i}]}}<br>"
        
        # Add work_mode before Time
        if work_mode_col:
            battery_hover += f"<b>Work Mode</b>: %{{customdata[{len(other_battery_cols)}]}}<br>"
        
        # Add time (last)
        battery_hover += f"<b>Time</b>: %{{x}}"
        
        # Prepare customdata (values for other columns, excluding battery_col itself)
        battery_customdata = []
        for _, row in day_df_sorted.iterrows():
            row_data = []
            for col in other_battery_cols:
                val = row[col] if pd.notna(row[col]) else 0
                row_data.append(f"{val:.2f}")
            if work_mode_col:
                row_data.append(str(row[work_mode_col]))
            battery_customdata.append(tuple(row_data))
        
        fig_battery.update_traces(hovertemplate=battery_hover, customdata=battery_customdata)
        fig_battery.update_layout(hovermode='closest', hoverdistance=-1)
        st.plotly_chart(fig_battery, use_container_width=True)
    else:
        st.warning("Battery Voltage column not found")

    # One main graph with AC Output Active Power Total - hover shows all values
    st.header("📊 AC Output Active Power Total (W) - Hover for all values")
    
    # Main column is AC Output Active Power Total (index 0 in key_params)
    main_col = None
    for col in display_cols:
        col_lower = col.lower()
        if 'ac_output_active_power_total' in col_lower:
            main_col = col
            break
    if main_col is None and display_cols:
        main_col = display_cols[0]  # Use first column as main if not found
    
    # Create hover_data dict - shows all parameters from key_params in hover with custom labels
    hover_data = {}
    for col in display_cols:
        if col != main_col:
            hover_data[col] = ':.2f'
    
    # Add time to hover
    hover_data[datetime_col] = ':%H:%M:%S'
    
    # Create main line chart
    fig_main = px.line(day_df_sorted, x=datetime_col, y=main_col,
                       title="AC Output Active Power Total",
                       markers=True,
                       hover_data=hover_data)
    
    # Build custom hover with friendly names - use hovertemplate
    # Main value
    main_label = custom_labels.get(main_col, main_col)
    hover_template = f"<b>{main_label}</b>: %{{y:.2f}}<br>"
    
    # Add other columns with their friendly names and values
    other_cols = [col for col in display_cols if col != main_col]
    for i, col in enumerate(other_cols):
        friendly_name = custom_labels.get(col, col)
        # Access customdata by index - need to use different approach
        hover_template += f"<b>{friendly_name}</b>: %{{customdata[{i}]}}<br>"
    
    # Add work_mode before Time (second to last)
    if work_mode_col:
        hover_template += f"<b>Work Mode</b>: %{{customdata[{len(other_cols)}]}}<br>"
    
    # Add time (last)
    hover_template += f"<b>Time</b>: %{{x}}"
    
    # Prepare customdata with all column values
    customdata_list = []
    for _, row in day_df_sorted.iterrows():
        row_data = []
        for col in other_cols:
            val = row[col] if pd.notna(row[col]) else 0
            row_data.append(f"{val:.2f}")
        # Add work_mode at the end if found
        if work_mode_col:
            row_data.append(str(row[work_mode_col]))
        customdata_list.append(tuple(row_data))
    
    # Update traces with custom template
    fig_main.update_traces(
        hovertemplate=hover_template,
        customdata=customdata_list
    )
    
    fig_main.update_layout(
        hovermode='closest',
        hoverdistance=-1
    )
    
    st.plotly_chart(fig_main, use_container_width=True)

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
    st.subheader("📊 Mode Timeline")
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
    col1.metric("Full Battery (≈100%)", f"{len(full_battery)} records - (V) ≥ 28.5V")
    
    # Low battery indicator
    low_battery = day_df[(day_df[voltage_col] < 24.0)]
    col2.metric("Low Battery (≈0-20%)", f"{len(low_battery)} records - (V) < 24V")

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

    # Raw Data
    with st.expander("View Raw Data"):
        st.dataframe(day_df)

else:
    st.info("Please upload an Excel file or enter a Google Sheet link to begin analysis.")

