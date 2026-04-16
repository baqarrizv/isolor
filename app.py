import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests
import os
from io import BytesIO

# Mobile-friendly page config
st.set_page_config(
    page_title="Inverter Analytics",
    page_icon="🔋",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for mobile responsiveness
st.markdown(""""
<style>
    /* Mobile-first responsive styles */
    @media (max-width: 768px) {
        .stApp {
            padding: 0.5rem;
        }
        .stTitle {
            font-size: 1.5rem !important;
        }
        .stHeader {
            font-size: 1.2rem !important;
        }
        div[data-testid="stMetric"] {
            padding: 0.5rem !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.8rem !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1rem !important;
        }
    }
    
    /* Make charts full width on mobile */
    div[data-testid="stPlotlyChart"] {
        width: 100%;
    }
    
    /* Better spacing for mobile */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        width: 100% !important;
    }
    
    /* Radio button horizontal on mobile */
    div[data-testid="stRadio"] > div {
        flex-direction: column;
    }
    
    /* Stack columns on small screens */
    div[data-testid="column"] {
        width: 100% !important;
        margin-bottom: 0.5rem;
    }
</style>

<script>
// Additional mobile responsive adjustments
function adjustForMobile() {
    const isMobile = window.innerWidth <= 768;
    
    // Stack all column groups vertically on mobile
    if (isMobile) {
        const columns = document.querySelectorAll('[data-testid="stHorizontalBlock"]');
        columns.forEach(col => {
            col.style.flexDirection = 'column';
            col.style.gap = '0.5rem';
        });
        
        // Make charts taller on mobile for better visibility
        const charts = document.querySelectorAll('[data-testid="stPlotlyChart"]');
        charts.forEach(chart => {
            chart.style.minHeight = '300px';
        });
    }
}

// Run on load and resize
window.addEventListener('load', adjustForMobile);
window.addEventListener('resize', adjustForMobile);
</script>
""", unsafe_allow_html=True)

st.title("🔋 Inverter Analytics")
st.markdown("Upload your inverter Excel file or use a Google Sheet link and get detailed hourly & daily insights.")

# Option to choose data source - Default is Google Sheet (collapsed by default)
with st.expander("📊 Data Source", expanded=False):
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
    
    # ===== DATE FILTER (MUST BE BEFORE SIDEBAR) =====
    date_options = sorted(df["date"].unique(), reverse=True)
    if len(date_options) == 0:
        st.error("⚠️ No valid dates found in the data.")
        st.stop()
    
    # ===== SIDEBAR =====
    # First: Calculation Method
    calc_method = st.sidebar.radio(
        "Calculation Method:",
        ["Fixed 5 Minutes", "Average Based"],
        index=0,
        horizontal=True,
        help="Fixed 5 Minutes: Uses 5 min per row. Average Based: Auto-detects time interval from data (default)."
    )
    
    # Second: Select Date
    selected_date = st.sidebar.selectbox("Select Date", date_options)
    
    # Energy calculation function
    def calculate_daily_energy(df, datetime_col, calc_method):
        df_calc = df.copy()
        df_calc = df_calc.fillna(0)
        
        if calc_method == "Fixed 5 Minutes":
            time_per_row_hours = 5 / 60  # 0.0833 hours
            st.sidebar.write(f"**Debug:** Each row = 5 minutes = {time_per_row_hours:.4f} hours")
        else:
            df_calc = df_calc.sort_values(datetime_col)
            time_diffs = df_calc[datetime_col].diff().dropna()
            
            if len(time_diffs) > 0:
                avg_minutes = time_diffs.mean().total_seconds() / 60
                time_per_row_hours = avg_minutes / 60
                st.sidebar.write(f"**Debug:** Auto-detected avg interval = {avg_minutes:.2f} min = {time_per_row_hours:.4f} hours")
            else:
                time_per_row_hours = 5 / 60
                st.sidebar.write(f"**Debug:** Could not detect, using fallback = 5 min = {time_per_row_hours:.4f} hours")
        
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
        
        st.sidebar.write(f"**Raw Solar Power Sum:** {total_solar_power} W")
        st.sidebar.write(f"**Solar kWh ({calc_method}):** {total_solar_kwh:.2f} kWh")
        st.sidebar.write(f"**Calculation:** {total_solar_power} × {time_per_row_hours:.4f} / 1000 = {total_solar_kwh:.2f} kWh")
        
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

    # Calculate daily energy
    daily_energy = calculate_daily_energy(df, datetime_col, calc_method)
    
    # Format the dataframe for better display
    daily_display = daily_energy.copy()
    daily_display['solar_kwh'] = daily_display['solar_kwh'].round(2)
    daily_display['utility_kwh'] = daily_display['utility_kwh'].round(2)
    daily_display['load_kwh'] = daily_display['load_kwh'].round(2)
    daily_display['battery_kwh'] = daily_display['battery_kwh'].round(2)
    
    # Rename columns for better display
    daily_display.columns = ['Date', 'Solar (kWh)', 'Grid (kWh)', 'Load (kWh)', 'Battery (kWh)', 'Records']
    
    # Note: selected_date is already set in sidebar above
    
    # ===== BREAKDOWN SECTION (DIRECT DISPLAY - BEFORE DAILY ENERGY CHART) =====
    st.subheader(f"📊 Breakdown in Units: {selected_date}")
    selected_day_data = daily_energy[daily_energy['date'] == selected_date]
    if len(selected_day_data) > 0:
        selected_day = selected_day_data.iloc[0]
        
        # Calculate total load: solar + grid + battery (battery is already included in load_kwh)
        # We need to show: Total Load = Load running from Grid + Load running from Battery
        # But load_kwh includes battery portion, so we need to show breakdown properly
        
        # Total main = Grid portion of load only (Grid consumed directly by load)
        # Backup = Battery portion (from load_kwh when running on battery)
        # Total = Main + Backup
        
        # Grid portion of load = total load - battery portion
        grid_portion_load = selected_day['load_kwh'] - selected_day['battery_kwh']
        
        col_a, col_b, col_c, col_d, col_e = st.columns(5)
        col_a.metric("☀️ Solar", f"{selected_day['solar_kwh']:.2f}")
        col_b.metric("⚡ Grid", f"{selected_day['utility_kwh']:.2f}")
        col_c.metric("🔋 Battery", f"{selected_day['battery_kwh']:.2f}")
        col_d.metric("🏠 Total Load", f"{selected_day['load_kwh']:.2f}")
        
        # Total = Solar + Grid + Battery (all power sources combined)
        total_all = selected_day['solar_kwh'] + selected_day['utility_kwh'] + selected_day['battery_kwh']
        col_e.metric("⚡ Total (Main)", f"{total_all:.2f}")
        
        # Calculate percentages - now including battery (round to 2 decimals)
        source_df = pd.DataFrame({
            'Source': ['☀️ Solar', '⚡ Grid', '🔋 Battery'],
            'Energy (kWh)': [round(selected_day['solar_kwh'], 2), round(selected_day['utility_kwh'], 2), round(selected_day['battery_kwh'], 2)]
        })

        fig_pie = px.pie(source_df, values='Energy (kWh)', names='Source',
                       title="Energy Sources",
                       color_discrete_sequence=['#FFD700', '#1E90FF', '#00CC96'],
                       category_orders={'Source': ['☀️ Solar', '⚡ Grid', '🔋 Battery']})
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(hoverlabel=dict(
            namelength=0,
            font_size=14
        ))
        # Update hovertemplate to show formatted values
        fig_pie.update_traces(
            hovertemplate='<b>%{label}</b><br>%{percent}<br>%{value:.2f} kWh', 
            texttemplate='<b>%{label}</b><br>%{value:.2f} kWh<br>%{percent}'
        )
        # Make chart responsive for mobile
        st.plotly_chart(fig_pie, use_container_width=True, config={
            'responsive': True,
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        })
    
    # ===== DAILY ENERGY CHART (NO EXPANDER - DIRECT DISPLAY) =====
    # Prepare data for custom hover - show all 4 values for the hovered date
    # Rename columns to friendly names for display
    daily_energy_display = daily_energy.rename(columns={
        'solar_kwh': '☀️ Solar',
        'utility_kwh': '⚡ Grid',
        'load_kwh': '🏠 Load',
        'battery_kwh': '🔋 Battery'
    })
    daily_energy_sorted = daily_energy_display.sort_values('date').reset_index(drop=True)
    
    # Get all energy values for each date using friendly column names
    solar_vals = daily_energy_sorted['☀️ Solar'].values
    grid_vals = daily_energy_sorted['⚡ Grid'].values
    load_vals = daily_energy_sorted['🏠 Load'].values
    battery_vals = daily_energy_sorted['🔋 Battery'].values
    dates = daily_energy_sorted['date'].values
    
    # Calculate total for each date (Solar + Grid + Battery = all sources)
    total_vals = solar_vals + grid_vals + battery_vals
    
    # Prepare customdata - each trace needs all 4 values for each date point
    # Format: [solar, grid, load, battery, total]
    customdata_all = []
    for i in range(len(dates)):
        customdata_all.append([
            round(solar_vals[i], 2),
            round(grid_vals[i], 2),
            round(load_vals[i], 2),
            round(battery_vals[i], 2),
            round(total_vals[i], 2)
        ])
    
    # Map trace names to friendly names with color indicators
    trace_names = {
        'Solar': '☀️ Solar',
        'Grid': '⚡ Grid',
        'Load': '🏠 Load',
        'Battery': '🔋 Battery'
    }
    
    # Build custom hover template with bar name and value first, then all 4 values + total
    custom_hover = (
        "<b>Date: %{x}</b><br>" +
        "<i>%{fullData.name}</i>: <b>%{y:.2f} kWh</b><br>" +
        "------<br>" +
        "Solar: <b>%{customdata[0]:.2f} kWh</b><br>" +
        "Grid: <b>%{customdata[1]:.2f} kWh</b><br>" +
        "Battery: <b>%{customdata[3]:.2f} kWh</b><br>" +
        "Load: <b>%{customdata[2]:.2f} kWh</b><br>"
    )
    
    # Create the bar chart with friendly column names
    fig_energy = px.bar(
        daily_energy_sorted, x='date', 
        y=['☀️ Solar', '⚡ Grid', '🏠 Load', '🔋 Battery'],
        title="Daily Energy: Solar vs Grid vs Load vs Battery (units)",
        barmode='group',
        labels={'date': 'Date', 'value': 'Units (kWh)', 'variable': 'Type'},
        color_discrete_map={
            '☀️ Solar': '#FFD700',
            '⚡ Grid': '#1E90FF',
            '🏠 Load': '#FF6347',
            '🔋 Battery': '#00CC96'
        }
    )
    
    # Apply custom hover to all traces
    fig_energy.update_traces(
        hovertemplate=custom_hover,
        customdata=customdata_all
    )
    fig_energy.update_layout(
        yaxis_title="Units (kWh)",
        hovermode="closest",
        hoverdistance=15
    )
    # Make chart responsive for mobile
    st.plotly_chart(fig_energy, use_container_width=True, config={
        'responsive': True,
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d']
    })
    
    # ===== ANALYSIS FOR SELECTED DATE (START) =====
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
    
    # Make chart responsive for mobile
    st.plotly_chart(fig_load, use_container_width=True, config={
        'responsive': True,
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d']
    })
    
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
    
    # Grid Voltage Graph (DIRECT DISPLAY - NO EXPANDER)
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
    
    # Make chart responsive for mobile
    st.plotly_chart(fig_voltage, use_container_width=True, config={
        'responsive': True,
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d']
    })
    
    # Battery Voltage Graph (DIRECT DISPLAY - NO EXPANDER)
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
        
        # Make chart responsive for mobile
        st.plotly_chart(fig_battery, use_container_width=True, config={
            'responsive': True,
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        })
    else:
        st.warning("Battery Voltage column not found")

    # AC Output Active Power Total (DIRECT DISPLAY - NO EXPANDER)
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
    
    # Make chart responsive for mobile
    st.plotly_chart(fig_main, use_container_width=True, config={
        'responsive': True,
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d']
    })

    # Solar Mode vs Grid Mode vs Battery Mode - Based on power values (DIRECT DISPLAY - NO EXPANDER)
    # Calculate mode times based on power values
    day_df[mode_col] = day_df[mode_col].astype(str)
    day_df = day_df.sort_values(datetime_col).reset_index(drop=True)
    
    # Get actual time span from first to last record in the day (more accurate)
    day_start = day_df[datetime_col].min()
    day_end = day_df[datetime_col].max()
    if pd.notna(day_start) and pd.notna(day_end):
        actual_time_span_hours = (day_end - day_start).total_seconds() / 3600
    else:
        actual_time_span_hours = 0
    
    # Get time interval for calculation
    if calc_method == "Fixed 5 Minutes":
        time_per_row_hours = 5 / 60
    else:
        full_df_sorted = df.sort_values(datetime_col)
        time_diffs = full_df_sorted[datetime_col].diff().dropna()
        if len(time_diffs) > 0:
            avg_minutes = time_diffs.mean().total_seconds() / 60
            time_per_row_hours = avg_minutes / 60
            st.sidebar.write(f"**Auto-detected interval:** {avg_minutes:.2f} min per row")
        else:
            time_per_row_hours = 5 / 60
    
    # Define modes based on power values:
    grid_records = day_df[day_df['grid_power_input_active_total'] > 0]
    solar_records = day_df[(day_df['grid_power_input_active_total'] == 0) & (day_df['pv_input_power_1'] > 0)]
    battery_records = day_df[(day_df['grid_power_input_active_total'] == 0) & 
                             (day_df['pv_input_power_1'] == 0) & 
                             (day_df['ac_output_active_power_total'] > 0)]
    
    # Calculate time for each mode using time interval per row (more accurate)
    grid_time_hours = len(grid_records) * time_per_row_hours
    solar_time_hours = len(solar_records) * time_per_row_hours
    battery_time_hours = len(battery_records) * time_per_row_hours
    
    # Total records in selected day
    total_records = len(day_df)
    actual_mode_total = grid_time_hours + solar_time_hours + battery_time_hours
    
    st.sidebar.write(f"**Actual time span:** {int(actual_time_span_hours)}h {int((actual_time_span_hours % 1) * 60)}min")
    st.sidebar.write(f"**Records in day:** {total_records}")
    st.sidebar.write(f"**Grid:** {len(grid_records)} records → {int(grid_time_hours)}h {int((grid_time_hours % 1) * 60)}min")
    st.sidebar.write(f"**Solar:** {len(solar_records)} records → {int(solar_time_hours)}h {int((solar_time_hours % 1) * 60)}min")
    st.sidebar.write(f"**Battery:** {len(battery_records)} records → {int(battery_time_hours)}h {int((battery_time_hours % 1) * 60)}min")
    st.sidebar.write(f"**Mode Total:** {int(actual_mode_total)}h {int((actual_mode_total % 1) * 60)}min")
    
    mode_data = pd.DataFrame({
        'Mode': ['☀️ Solar', '⚡ Grid', '🔋 Battery'],
        'Hours': [solar_time_hours, grid_time_hours, battery_time_hours],
        'Hours_Display': [f"{int(solar_time_hours)}h {int(round((solar_time_hours % 1) * 60))}m", f"{int(grid_time_hours)}h {int(round((grid_time_hours % 1) * 60))}m", f"{int(battery_time_hours)}h {int(round((battery_time_hours % 1) * 60))}m"],
        'Records': [len(solar_records), len(grid_records), len(battery_records)]
    })
    fig_mode = px.bar(mode_data, x='Mode', y='Hours', title="Total Time in Each Mode", color='Mode',
                      color_discrete_map={'☀️ Solar': '#FFD700', '⚡ Grid': '#1E90FF', '🔋 Battery': '#00CC96'})
    fig_mode.update_layout(yaxis_title="Hours")
    
    # Set text for each bar individually
    for i, trace in enumerate(fig_mode.data):
        trace.text = [mode_data['Hours_Display'].iloc[i]]
        trace.textposition = 'outside'
        trace.hovertemplate = f'<b>{mode_data["Mode"].iloc[i]}</b><br>Time: {mode_data["Hours_Display"].iloc[i]}<br>Records: {mode_data["Records"].iloc[i]}'
    
    # Make chart responsive for mobile
    st.plotly_chart(fig_mode, use_container_width=True, config={
        'responsive': True,
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d']
    })
    
    col1, col2, col3 = st.columns(3)
    col1.metric("☀️ Solar Time", f"{int(solar_time_hours)}h {int((solar_time_hours % 1) * 60)}m")
    col2.metric("⚡ Grid Time", f"{int(grid_time_hours)}h {int((grid_time_hours % 1) * 60)}m")
    col3.metric("🔋 Battery Time", f"{int(battery_time_hours)}h {int((battery_time_hours % 1) * 60)}m")

    # ===== MODE TIMELINE - Show Start Time and End Time for each period =====
    st.subheader("🕐 Mode Timeline - Start & End Times")
    
    day_df_timeline = day_df.sort_values(datetime_col).reset_index(drop=True)
    
    def get_mode(row):
        if row['grid_power_input_active_total'] > 0:
            return 'grid'
        elif row['pv_input_power_1'] > 0:
            return 'solar'
        elif row['ac_output_active_power_total'] > 0:
            return 'battery'
        else:
            return 'idle'
    
    day_df_timeline['mode'] = day_df_timeline.apply(get_mode, axis=1)
    
    def find_continuous_periods(df, mode):
        mode_df = df[df['mode'] == mode].copy()
        if len(mode_df) == 0:
            return []
        
        periods = []
        mode_df = mode_df.sort_values(datetime_col).reset_index(drop=True)
        
        start_time = mode_df.iloc[0][datetime_col]
        prev_time = start_time
        
        for i in range(1, len(mode_df)):
            current_time = mode_df.iloc[i][datetime_col]
            time_diff_minutes = (current_time - prev_time).total_seconds() / 60
            
            if time_diff_minutes > (time_per_row_hours * 60 * 1.5):
                end_time = mode_df.iloc[i-1][datetime_col]
                duration_hours = (end_time - start_time).total_seconds() / 3600
                periods.append({
                    'start': start_time,
                    'end': end_time,
                    'duration_hours': duration_hours
                })
                start_time = current_time
            
            prev_time = current_time
        
        end_time = mode_df.iloc[-1][datetime_col]
        duration_hours = (end_time - start_time).total_seconds() / 3600
        periods.append({
            'start': start_time,
            'end': end_time,
            'duration_hours': duration_hours
        })
        
        return periods
    
    solar_periods = find_continuous_periods(day_df_timeline, 'solar')
    grid_periods = find_continuous_periods(day_df_timeline, 'grid')
    battery_periods = find_continuous_periods(day_df_timeline, 'battery')
    
    def format_duration(hours):
        h = int(hours)
        m = int((hours % 1) * 60)
        return f"{h}h {m}m"
    
    def format_time(dt):
        return dt.strftime('%H:%M')
    
    col_solar, col_grid, col_battery = st.columns(3)
    
    with col_solar:
        st.markdown("#### ☀️ Solar")
        if solar_periods:
            for i, p in enumerate(solar_periods):
                st.write(f"**Period {i+1}:**")
                st.write(f"⏰ {format_time(p['start'])} - {format_time(p['end'])}")
                st.write(f"⏱️ Duration: {format_duration(p['duration_hours'])}")
                st.divider()
            st.success(f"Total: {format_duration(solar_time_hours)}")
        else:
            st.info("No solar period")
    
    with col_grid:
        st.markdown("#### ⚡ Grid")
        if grid_periods:
            for i, p in enumerate(grid_periods):
                st.write(f"**Period {i+1}:**")
                st.write(f"⏰ {format_time(p['start'])} - {format_time(p['end'])}")
                st.write(f"⏱️ Duration: {format_duration(p['duration_hours'])}")
                st.divider()
            st.success(f"Total: {format_duration(grid_time_hours)}")
        else:
            st.info("No grid period")
    
    with col_battery:
        st.markdown("#### 🔋 Battery")
        if battery_periods:
            for i, p in enumerate(battery_periods):
                st.write(f"**Period {i+1}:**")
                st.write(f"⏰ {format_time(p['start'])} - {format_time(p['end'])}")
                st.write(f"⏱️ Duration: {format_duration(p['duration_hours'])}")
                st.divider()
            st.success(f"Total: {format_duration(battery_time_hours)}")
        else:
            st.info("No battery period")

    # ===== DUAL SUPPLY ANALYSIS - Solar + Grid Load Distribution =====
    st.subheader("⚡⚡ Dual Supply Analysis - Load Distribution")
    
    day_df_dual = day_df_timeline.copy()
    
    def classify_power_source(row):
        solar = row.get('pv_input_power_1', 0) or 0
        grid = row.get('grid_power_input_active_total', 0) or 0
        load = row.get('ac_output_active_power_total', 0) or 0
        
        if load == 0:
            return 'idle'
        elif solar > 0 and grid > 0:
            return 'solar_grid'
        elif solar > 0 and grid == 0:
            return 'solar_only'
        elif grid > 0 and solar == 0:
            return 'grid_only'
        elif solar == 0 and grid == 0 and load > 0:
            return 'battery_only'
        else:
            return 'other'
    
    day_df_dual['power_source'] = day_df_dual.apply(classify_power_source, axis=1)
    
    dual_records = day_df_dual[day_df_dual['power_source'] == 'solar_grid']
    solar_only_records = day_df_dual[day_df_dual['power_source'] == 'solar_only']
    grid_only_records = day_df_dual[day_df_dual['power_source'] == 'grid_only']
    battery_only_records = day_df_dual[day_df_dual['power_source'] == 'battery_only']
    
    dual_time = len(dual_records) * time_per_row_hours
    solar_only_time = len(solar_only_records) * time_per_row_hours
    grid_only_time = len(grid_only_records) * time_per_row_hours
    battery_only_time = len(battery_only_records) * time_per_row_hours
    
    dual_load_kwh = (dual_records['ac_output_active_power_total'].sum() * time_per_row_hours / 1000) if len(dual_records) > 0 else 0
    solar_only_load_kwh = (solar_only_records['ac_output_active_power_total'].sum() * time_per_row_hours / 1000) if len(solar_only_records) > 0 else 0
    grid_only_load_kwh = (grid_only_records['ac_output_active_power_total'].sum() * time_per_row_hours / 1000) if len(grid_only_records) > 0 else 0
    battery_only_load_kwh = (battery_only_records['ac_output_active_power_total'].sum() * time_per_row_hours / 1000) if len(battery_only_records) > 0 else 0
    
    solar_contribution_kwh = (dual_records['pv_input_power_1'].sum() * time_per_row_hours / 1000) if len(dual_records) > 0 else 0
    grid_contribution_kwh = (dual_records['grid_power_input_active_total'].sum() * time_per_row_hours / 1000) if len(dual_records) > 0 else 0
    
    st.markdown("### 📊 Power Source Distribution")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("☀️⚡ Solar+Grid", f"{format_duration(dual_time)}")
    col2.metric("☀️ Solar Only", f"{format_duration(solar_only_time)}")
    col3.metric("⚡ Grid Only", f"{format_duration(grid_only_time)}")
    col4.metric("🔋 Battery Only", f"{format_duration(battery_only_time)}")
    
    st.markdown("### 📈 Load Distribution (kWh)")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("☀️⚡ Total Load", f"{dual_load_kwh + solar_only_load_kwh + grid_only_load_kwh + battery_only_load_kwh:.2f} kWh")
    col2.metric("☀️⚡ Solar Source", f"{solar_only_load_kwh + solar_contribution_kwh:.2f} kWh")
    col3.metric("⚡⚡ Grid Source", f"{grid_only_load_kwh + grid_contribution_kwh:.2f} kWh")
    col4.metric("🔋 Battery Source", f"{battery_only_load_kwh:.2f} kWh")
    
    st.markdown("### 🔍 Dual Supply Periods Detail (Solar + Grid Together)")
    
    if len(dual_records) > 0:
        dual_sorted = dual_records.sort_values(datetime_col).reset_index(drop=True)
        
        dual_periods = []
        if len(dual_sorted) > 0:
            start_time = dual_sorted.iloc[0][datetime_col]
            prev_time = start_time
            
            for i in range(1, len(dual_sorted)):
                current_time = dual_sorted.iloc[i][datetime_col]
                time_diff_minutes = (current_time - prev_time).total_seconds() / 60
                
                if time_diff_minutes > (time_per_row_hours * 60 * 1.5):
                    end_time = dual_sorted.iloc[i-1][datetime_col]
                    period_records = dual_sorted[(dual_sorted[datetime_col] >= start_time) & (dual_sorted[datetime_col] <= end_time)]
                    period_load_kwh = period_records['ac_output_active_power_total'].sum() * time_per_row_hours / 1000
                    period_solar_kwh = period_records['pv_input_power_1'].sum() * time_per_row_hours / 1000
                    period_grid_kwh = period_records['grid_power_input_active_total'].sum() * time_per_row_hours / 1000
                    
                    duration_hours = (end_time - start_time).total_seconds() / 3600
                    dual_periods.append({
                        'start': start_time,
                        'end': end_time,
                        'duration_hours': duration_hours,
                        'load_kwh': period_load_kwh,
                        'solar_kwh': period_solar_kwh,
                        'grid_kwh': period_grid_kwh
                    })
                    start_time = current_time
                
                prev_time = current_time
            
            if len(dual_sorted) > 0:
                end_time = dual_sorted.iloc[-1][datetime_col]
                period_records = dual_sorted[(dual_sorted[datetime_col] >= start_time) & (dual_sorted[datetime_col] <= end_time)]
                period_load_kwh = period_records['ac_output_active_power_total'].sum() * time_per_row_hours / 1000
                period_solar_kwh = period_records['pv_input_power_1'].sum() * time_per_row_hours / 1000
                period_grid_kwh = period_records['grid_power_input_active_total'].sum() * time_per_row_hours / 1000
                
                duration_hours = (end_time - start_time).total_seconds() / 3600
                dual_periods.append({
                    'start': start_time,
                    'end': end_time,
                    'duration_hours': duration_hours,
                    'load_kwh': period_load_kwh,
                    'solar_kwh': period_solar_kwh,
                    'grid_kwh': period_grid_kwh
                })
        
        if dual_periods:
            for i, p in enumerate(dual_periods):
                with st.expander(f"Period {i+1}: {format_time(p['start'])} - {format_time(p['end'])} ({format_duration(p['duration_hours'])})"):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Total Load", f"{p['load_kwh']:.2f} kWh")
                    col_b.metric("☀️ Solar Contribution", f"{p['solar_kwh']:.2f} kWh")
                    col_c.metric("⚡ Grid Contribution", f"{p['grid_kwh']:.2f} kWh")
                    
                    if p['load_kwh'] > 0:
                        solar_pct = (p['solar_kwh'] / p['load_kwh']) * 100
                        grid_pct = (p['grid_kwh'] / p['load_kwh']) * 100
                        st.progress(int(min(solar_pct, 100)))
                        st.write(f"Solar: {solar_pct:.1f}% | Grid: {grid_pct:.1f}%")
        else:
            st.info("No dual supply periods found")
    else:
        st.info("No time period found when both Solar and Grid were providing power together")

    # ===== DAILY ENERGY SUMMARY (AT END - COLLAPSED BY DEFAULT) =====
    with st.expander("📊 Daily Energy Summary", expanded=False):
        st.dataframe(daily_display, use_container_width=True)
    
    # ===== OTHER SECTIONS (AT END - COLLAPSED BY DEFAULT) =====
    # Battery Status
    with st.expander("🔋 Battery Status", expanded=False):
        full_battery = day_df[(day_df[voltage_col] >= 28.5)]
        col1, col2 = st.columns(2)
        col1.metric("Full Battery (≈100%)", f"{len(full_battery)} records - (V) ≥ 28.5V")
        
        low_battery = day_df[(day_df[voltage_col] < 24.0)]
        col2.metric("Low Battery (≈0-20%)", f"{len(low_battery)} records - (V) < 24V")

    # Performance Score
    with st.expander("📊 Inverter Performance", expanded=False):
        # Battery mode now includes only records where load is running from battery
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
