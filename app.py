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
    
    # If user uploaded a file, use it. Otherwise check for local file.
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            st.success(f"Loaded uploaded file: {uploaded_file.name} ✅")
        except Exception as e:
            st.error(f"Error reading uploaded file: {e}")
    else:
        # Check if local file exists and load it
        local_file = 'simplefile.xlsx'
        if os.path.exists(local_file):
            try:
                df = pd.read_excel(local_file)
                st.success(f"Loaded local file: {local_file} ✅")
            except Exception as e:
                st.warning(f"Could not load local file: {e}")

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

    # ===== DAILY ENERGY SUMMARY SECTION =====
    with st.expander("📊 Daily Energy Summary", expanded=False):
        # Option to choose calculation method: Fixed 5 min or Average based
        calc_method = st.sidebar.radio(
            "Calculation Method:",
            ["Fixed 5 Minutes", "Average Based"],
            index=0,
            horizontal=True,
            help="Fixed 5 Minutes: Uses 5 min per row. Average Based: Auto-detects time interval from data (default)."
        )

        # Energy calculation function
        def calculate_daily_energy(df, datetime_col, calc_method):
            df_calc = df.copy()
            df_calc = df_calc.fillna(0)
            
            if calc_method == "Fixed 5 Minutes":
                time_per_row_hours = 5 / 60  # 0.0833 hours
                st.write(f"Debug: Each row = 5 minutes = {time_per_row_hours:.4f} hours")
            else:
                df_calc = df_calc.sort_values(datetime_col)
                time_diffs = df_calc[datetime_col].diff().dropna()
                
                if len(time_diffs) > 0:
                    avg_minutes = time_diffs.mean().total_seconds() / 60
                    time_per_row_hours = avg_minutes / 60
                    st.write(f"Debug: Auto-detected average interval = {avg_minutes:.2f} minutes = {time_per_row_hours:.4f} hours")
                else:
                    time_per_row_hours = 5 / 60
                    st.write(f"Debug: Could not detect, using fallback = 5 minutes = {time_per_row_hours:.4f} hours")
            
            # Energy (kWh) = Power (W) × time_per_row_hours / 1000
            df_calc['solar_kwh'] = df_calc['pv_input_power_1'] * time_per_row_hours / 1000
            df_calc['utility_kwh'] = df_calc['grid_power_input_active_total'] * time_per_row_hours / 1000
            df_calc['load_kwh'] = df_calc['ac_output_active_power_total'] * time_per_row_hours / 1000
            
            # Battery energy calculation:
            # When pv_input_power_1 = 0 AND grid_power_input_active_total = 0 AND ac_output_active_power_total > 0
            # Then load is running from battery
            df_calc['battery_kwh'] = 0.0
            battery_condition = (
                (df_calc['pv_input_power_1'] == 0) & 
                (df_calc['grid_power_input_active_total'] == 0) & 
                (df_calc['ac_output_active_power_total'] > 0)
            )
            df_calc.loc[battery_condition, 'battery_kwh'] = df_calc.loc[battery_condition, 'ac_output_active_power_total'] * time_per_row_hours / 1000
            
            total_solar_power = df_calc['pv_input_power_1'].sum()
            total_solar_kwh = df_calc['solar_kwh'].sum()
            
            st.write(f"Raw Solar Power Sum = {total_solar_power} W")
            st.write(f"Solar kWh (using {calc_method}) = {total_solar_kwh:.2f} kWh")
            st.write(f"Calculation: {total_solar_power} × {time_per_row_hours:.4f} / 1000 = {total_solar_kwh:.2f} kWh")
            
            # Group by date
            daily = df_calc.groupby('date').agg({
                'solar_kwh': 'sum',
                'utility_kwh': 'sum', 
                'load_kwh': 'sum',
                'battery_kwh': 'sum'
            }).reset_index()
            
            # Count records per day
            record_counts = df_calc.groupby('date').size().reset_index(name='total_records')
            daily = daily.merge(record_counts, on='date')
            
            return daily

        # Calculate and display
        daily_energy = calculate_daily_energy(df, datetime_col, calc_method)
        
        # Format the dataframe for better display
        daily_display = daily_energy.copy()
        daily_display['solar_kwh'] = daily_display['solar_kwh'].round(2)
        daily_display['utility_kwh'] = daily_display['utility_kwh'].round(2)
        daily_display['load_kwh'] = daily_display['load_kwh'].round(2)
        daily_display['battery_kwh'] = daily_display['battery_kwh'].round(2)
        
        # Rename columns for better display
        daily_display.columns = ['Date', 'Solar (kWh)', 'Grid (kWh)', 'Load (kWh)', 'Battery (kWh)', 'Records']
        
        st.dataframe(daily_display, use_container_width=True)
    
    # Sidebar date filter - moved before breakdown
    date_options = sorted(df["date"].unique(), reverse=True)
    if len(date_options) == 0:
        st.error("⚠️ No valid dates found in the data.")
        st.stop()
    
    selected_date = st.sidebar.selectbox("Select Date", date_options)
    
    # Show detailed breakdown for the selected date (Collapsed by default)
    with st.expander(f"📊 Breakdown: {selected_date}", expanded=False):
        selected_day_data = daily_energy[daily_energy['date'] == selected_date]
        if len(selected_day_data) > 0:
            selected_day = selected_day_data.iloc[0]
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("☀️ Solar se", f"{selected_day['solar_kwh']:.2f} units")
            col_b.metric("⚡ Grid se", f"{selected_day['utility_kwh']:.2f} units")
            col_d.metric("🔋 Battery se", f"{selected_day['battery_kwh']:.2f} units")
            col_c.metric("🏠 Total Load", f"{selected_day['load_kwh']:.2f} units")
            

            # Calculate percentages - now including battery
            source_df = pd.DataFrame({
                'Source': ['☀️ Solar', '⚡ Grid', '🔋 Battery'],
                'Energy (kWh)': [selected_day['solar_kwh'], selected_day['utility_kwh'], selected_day['battery_kwh']]
            })

            fig_pie = px.pie(source_df, values='Energy (kWh)', names='Source',
                           title="Energy Sources")
            st.plotly_chart(fig_pie, use_container_width=True)

    # Bar chart - Solar vs Grid vs Load vs Battery (Collapsed by default)
    with st.expander("📊 Daily Energy Chart", expanded=False):
        fig_energy = px.bar(
            daily_energy, x='date', 
            y=['solar_kwh', 'utility_kwh', 'load_kwh', 'battery_kwh'],
            title="Daily Energy: Solar vs Grid vs Load vs Battery (units)",
            barmode='group',
            labels={'date': 'Date', 'value': 'Units (kWh)', 'variable': 'Type'},
            color_discrete_map={
                'solar_kwh': '#FFD700',
                'utility_kwh': '#1E90FF',
                'load_kwh': '#FF6347',
                'battery_kwh': '#00CC96'
            }
        )
        fig_energy.update_layout(yaxis_title="Units (kWh)")
        st.plotly_chart(fig_energy, use_container_width=True)
    
    # Analysis for selected date
    day_df = df[df["date"] == selected_date]

    if len(day_df) == 0:
        st.warning("No data available for the selected date.")
        st.stop()

    st.header(f"📅 Analysis for {selected_date}")
    
    # Option to view load as hourly average or row-wise
    load_view_mode = st.radio("Load View Mode:", ["Hourly Average", "Row-wise (Every Entry)"], horizontal=True, index=1)
    
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
    
    # Key parameters to show in hover
    key_params = [
        'ac_output_active_power_total',
        'ac_output_load_r',
        'ac_output_load_total',
        'pv_input_power_1',
        'discharging_current',
        'grid_power_input_active_total',
        'work_mode',
        'battery_voltage',
        load_col
    ]
    
    # Custom display names for hover
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
    
    # Filter numeric columns
    display_cols = []
    for col in numeric_cols:
        col_lower = col.lower()
        if col_lower in key_params:
            display_cols.append(col)
        if col == load_col and col not in display_cols:
            display_cols.append(col)
    
    # Also check for work_mode in all columns
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
    
    # Grid Voltage Graph
    st.subheader("📈 Grid Voltage Trend")
    
    # Create voltage chart with custom hover (like Load Output chart)
    fig_voltage = px.line(day_df_sorted, x=datetime_col, y=voltage_col,
                         title="Grid Voltage Trend",
                         markers=True)
    
    # Build custom hover with key params - voltage value first, then others
    voltage_hover = f"<b>Grid Voltage</b>: %{{y:.2f}} V<br>"
    
    # Add other columns to hover (excluding voltage_col and datetime_col)
    hover_cols_for_voltage = []
    for col in display_cols:
        if col.lower() != voltage_col.lower() and col not in [datetime_col, 'date', 'hour']:
            hover_cols_for_voltage.append(col)
    
    for i, col in enumerate(hover_cols_for_voltage):
        friendly = custom_labels.get(col, col)
        voltage_hover += f"<b>{friendly}</b>: %{{customdata[{i}]}}<br>"
    
    if work_mode_col:
        voltage_hover += f"<b>Work Mode</b>: %{{customdata[{len(hover_cols_for_voltage)}]}}<br>"
    voltage_hover += f"<b>Time</b>: %{{x}}"
    
    # Prepare customdata
    voltage_customdata = []
    for _, row in day_df_sorted.iterrows():
        row_data = []
        for col in hover_cols_for_voltage:
            val = row[col] if pd.notna(row[col]) else 0
            row_data.append(f"{val:.2f}")
        if work_mode_col:
            row_data.append(str(row[work_mode_col]))
        voltage_customdata.append(tuple(row_data))
    
    fig_voltage.update_traces(hovertemplate=voltage_hover, customdata=voltage_customdata)
    fig_voltage.update_layout(hovermode='closest', hoverdistance=-1)
    
    st.plotly_chart(fig_voltage, use_container_width=True)
    
    # Battery Voltage Graph
    st.subheader("🔋 Battery Voltage Trend")
    
    battery_col = None
    for col in day_df_sorted.columns:
        if 'battery_voltage' in col.lower():
            battery_col = col
            break
    
    if battery_col:
        # Create battery chart with custom hover (like Grid Voltage chart)
        fig_battery = px.line(day_df_sorted, x=datetime_col, y=battery_col,
                             title="Battery Voltage Trend",
                             markers=True)
        
        # Build custom hover with key params - battery voltage value first, then others
        battery_hover = f"<b>Battery Voltage</b>: %{{y:.2f}} V<br>"
        
        # Add other columns to hover (excluding battery_col and datetime_col)
        hover_cols_for_battery = []
        for col in display_cols:
            col_lower = col.lower() if isinstance(col, str) else ''
            battery_col_lower = battery_col.lower() if isinstance(battery_col, str) else ''
            if col_lower != battery_col_lower and col not in [datetime_col, 'date', 'hour']:
                hover_cols_for_battery.append(col)
        
        for i, col in enumerate(hover_cols_for_battery):
            friendly = custom_labels.get(col, col)
            battery_hover += f"<b>{friendly}</b>: %{{customdata[{i}]}}<br>"
        
        if work_mode_col:
            battery_hover += f"<b>Work Mode</b>: %{{customdata[{len(hover_cols_for_battery)}]}}<br>"
        battery_hover += f"<b>Time</b>: %{{x}}"
        
        # Prepare customdata
        battery_customdata = []
        for _, row in day_df_sorted.iterrows():
            row_data = []
            for col in hover_cols_for_battery:
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

    # AC Output Active Power Total
    st.header("📊 AC Output Active Power Total (W)")
    
    main_col = None
    for col in display_cols:
        col_lower = col.lower()
        if 'ac_output_active_power_total' in col_lower:
            main_col = col
            break
    if main_col is None and display_cols:
        main_col = display_cols[0]
    
    # Create AC Output chart with custom hover (like Grid Voltage chart)
    fig_main = px.line(day_df_sorted, x=datetime_col, y=main_col,
                       title="AC Output Active Power Total",
                       markers=True)
    
    # Build custom hover with key params - AC Output value first, then others
    ac_hover = f"<b>AC Output Power</b>: %{{y:.2f}} W<br>"
    
    # Add other columns to hover (excluding main_col and datetime_col)
    hover_cols_for_ac = []
    for col in display_cols:
        col_lower = col.lower() if isinstance(col, str) else ''
        main_col_lower = main_col.lower() if isinstance(main_col, str) else ''
        if col_lower != main_col_lower and col not in [datetime_col, 'date', 'hour']:
            hover_cols_for_ac.append(col)
    
    for i, col in enumerate(hover_cols_for_ac):
        friendly = custom_labels.get(col, col)
        ac_hover += f"<b>{friendly}</b>: %{{customdata[{i}]}}<br>"
    
    if work_mode_col:
        ac_hover += f"<b>Work Mode</b>: %{{customdata[{len(hover_cols_for_ac)}]}}<br>"
    ac_hover += f"<b>Time</b>: %{{x}}"
    
    # Prepare customdata
    ac_customdata = []
    for _, row in day_df_sorted.iterrows():
        row_data = []
        for col in hover_cols_for_ac:
            val = row[col] if pd.notna(row[col]) else 0
            row_data.append(f"{val:.2f}")
        if work_mode_col:
            row_data.append(str(row[work_mode_col]))
        ac_customdata.append(tuple(row_data))
    
    fig_main.update_traces(hovertemplate=ac_hover, customdata=ac_customdata)
    fig_main.update_layout(hovermode='closest', hoverdistance=-1)
    
    st.plotly_chart(fig_main, use_container_width=True)

    # Solar Mode vs Grid Mode vs Battery Mode - Based on power values
    day_df[mode_col] = day_df[mode_col].astype(str)
    day_df = day_df.sort_values(datetime_col).reset_index(drop=True)
    day_df['time_diff'] = day_df[datetime_col].diff().dt.total_seconds() / 3600
    day_df['time_diff'] = day_df['time_diff'].fillna(1/60)
    
    # Define modes based on power values (mutually exclusive):
    # - Grid: grid_power_input_active_total > 0
    # - Solar: grid = 0 AND pv_input_power_1 > 0
    # - Battery: grid = 0 AND pv_input_power_1 = 0
    
    grid_records = day_df[day_df['grid_power_input_active_total'] > 0]
    solar_records = day_df[(day_df['grid_power_input_active_total'] == 0) & (day_df['pv_input_power_1'] > 0)]
    battery_records = day_df[(day_df['grid_power_input_active_total'] == 0) & (day_df['pv_input_power_1'] == 0)]
    
    grid_time_hours = grid_records['time_diff'].sum() if len(grid_records) > 0 else 0
    solar_time_hours = solar_records['time_diff'].sum() if len(solar_records) > 0 else 0
    battery_time_hours = battery_records['time_diff'].sum() if len(battery_records) > 0 else 0
    
    # Solar Mode vs Grid Mode vs Battery Mode - Based on power values (Collapsed by default)
    with st.expander("⚡ Inverter Operation Mode Time Calculation", expanded=False):
        
        mode_data = pd.DataFrame({
            'Mode': ['☀️ Solar', '⚡ Grid', '🔋 Battery'],
            'Hours': [solar_time_hours, grid_time_hours, battery_time_hours],
            'Records': [len(solar_records), len(grid_records), len(battery_records)]
        })
        fig_mode = px.bar(mode_data, x='Mode', y='Hours', title="Total Time in Each Mode", color='Mode',
                          color_discrete_map={'☀️ Solar': '#FFD700', '⚡ Grid': '#1E90FF', '🔋 Battery': '#00CC96'})
        fig_mode.update_layout(yaxis_title="Hours")
        st.plotly_chart(fig_mode, use_container_width=True)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("☀️ Solar Time", f"{round(solar_time_hours, 2)} hours")
        col2.metric("⚡ Grid Time", f"{round(grid_time_hours, 2)} hours")
        col3.metric("🔋 Battery Time", f"{round(battery_time_hours, 2)} hours")

    # Battery Status
    with st.expander("🔋 Battery Status", expanded=False):
        full_battery = day_df[(day_df[voltage_col] >= 28.5)]
        col1, col2 = st.columns(2)
        col1.metric("Full Battery (≈100%)", f"{len(full_battery)} records - (V) ≥ 28.5V")
        
        low_battery = day_df[(day_df[voltage_col] < 24.0)]
        col2.metric("Low Battery (≈0-20%)", f"{len(low_battery)} records - (V) < 24V")

    # Performance Score
    with st.expander("📊 Inverter Performance", expanded=False):
        battery_mode_time = len(battery_records)
        
        performance_score = (
            (len(full_battery) / len(day_df)) * 40 + 
            (len(grid_records) / len(day_df)) * 30 + 
            (1 - (battery_mode_time / len(day_df))) * 30
        )

        st.progress(int(performance_score))
        st.write(f"**Score: {round(performance_score,2)} / 100**")
        
        if performance_score >= 70:
            st.success("✅ Great performance! Inverter is working efficiently.")
        elif performance_score >= 40:
            st.warning("⚠️ Average performance. Check battery charging.")
        else:
            st.error("❌ Poor performance. Needs attention!")

    # Raw Data
    with st.expander("View Raw Data", expanded=False):
        st.dataframe(day_df)

else:
    st.info("Please upload an Excel file or enter a Google Sheet link to begin analysis.")
