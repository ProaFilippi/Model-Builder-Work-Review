"""
Streamlit App for Developer Work Time Analysis
Analyzes activity logs and generates work time reports
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import io

# Import functions from analyze_work_time
from analyze_work_time import (
    process_work_chunks,
    generate_summary,
    export_excel
)


def load_uploaded_logs(uploaded_files):
    """
    Loads logs from uploaded files.

    Args:
        uploaded_files: List of uploaded file objects from Streamlit

    Returns:
        Combined DataFrame with all logs
    """
    all_dfs = []

    for uploaded_file in uploaded_files:
        try:
            # Read as TSV (tab-separated)
            df = pd.read_csv(uploaded_file, sep='\t', encoding='utf-8', low_memory=False)
            df['_source_file'] = uploaded_file.name
            all_dfs.append(df)
            st.success(f"✓ Loaded {uploaded_file.name}: {len(df):,} logs")
        except Exception as e:
            st.error(f"❌ Error loading {uploaded_file.name}: {e}")
            return None

    if len(all_dfs) > 1:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        st.info(f"📊 Combined total: {len(combined_df):,} logs from {len(uploaded_files)} file(s)")
    else:
        combined_df = all_dfs[0]

    return combined_df


def create_excel_download(chunks_df, summary_df, inactivity_minutes):
    """Creates Excel file in memory for download."""
    output = io.BytesIO()

    # Prepare data for export
    chunks_export = chunks_df.copy()
    chunks_export['Start'] = chunks_export['Start'].dt.strftime('%Y-%m-%d %H:%M:%S')
    chunks_export['End'] = chunks_export['End'].dt.strftime('%Y-%m-%d %H:%M:%S')
    chunks_export = chunks_export.round(2)

    # Create pivot by day by developer
    chunks_with_date = chunks_df.copy()
    chunks_with_date['Date'] = chunks_with_date['Start'].dt.date

    pivot_by_day = chunks_with_date.groupby(['Date', 'Developer']).agg({
        'Duration (hours)': 'sum',
        'Log Count': 'sum',
        'Start': 'count'
    }).rename(columns={'Start': 'Chunk Count'}).reset_index()

    pivot_by_day = pivot_by_day.round(2)
    pivot_by_day = pivot_by_day.sort_values(['Date', 'Developer'])

    # Create pivot table (developers as columns)
    pivot_table = pivot_by_day.pivot_table(
        index='Date',
        columns='Developer',
        values='Duration (hours)',
        aggfunc='sum',
        fill_value=0
    ).round(2)

    # Add totals
    pivot_table['TOTAL'] = pivot_table.sum(axis=1).round(2)
    pivot_table.loc['TOTAL'] = pivot_table.sum(axis=0).round(2)

    # Create pivot by week
    chunks_with_week = chunks_df.copy()
    chunks_with_week['Week'] = chunks_with_week['Start'].dt.strftime('%Y-W%U')
    chunks_with_week['Week_Start'] = chunks_with_week['Start'].dt.to_period('W').dt.start_time

    pivot_by_week = chunks_with_week.groupby(['Week', 'Week_Start', 'Developer']).agg({
        'Duration (hours)': 'sum',
        'Log Count': 'sum',
        'Start': 'count'
    }).rename(columns={'Start': 'Chunk Count'}).reset_index()

    pivot_by_week = pivot_by_week.round(2)
    pivot_by_week['Week_Start'] = pivot_by_week['Week_Start'].dt.strftime('%Y-%m-%d')

    pivot_table_week = pivot_by_week.pivot_table(
        index='Week_Start',
        columns='Developer',
        values='Duration (hours)',
        aggfunc='sum',
        fill_value=0
    ).round(2)

    # Add totals to week pivot
    pivot_table_week['TOTAL'] = pivot_table_week.sum(axis=1).round(2)
    pivot_table_week.loc['TOTAL'] = pivot_table_week.sum(axis=0).round(2)

    # Create Excel writer
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Tab 1: Summary
        summary_df.to_excel(writer, sheet_name='Summary', index=True)

        # Tab 2: Pivot by Day
        pivot_table.to_excel(writer, sheet_name='Pivot - Hours by Day', index=True)

        # Tab 3: Pivot by Week
        pivot_table_week.to_excel(writer, sheet_name='Pivot - Hours by Week', index=True)

        # Tab 4: Details by Day
        pivot_by_day.to_excel(writer, sheet_name='Work by Day', index=False)

        # Tab 5: Details by Week
        pivot_by_week_export = pivot_by_week[['Week_Start', 'Developer', 'Duration (hours)', 'Log Count', 'Chunk Count']]
        pivot_by_week_export = pivot_by_week_export.sort_values(['Week_Start', 'Developer'])
        pivot_by_week_export.to_excel(writer, sheet_name='Work by Week', index=False)

        # Tab 6: All Chunks
        chunks_export.to_excel(writer, sheet_name='All Chunks', index=False)

        # Tabs 7+: One for each developer
        for developer in chunks_df['Developer'].unique():
            dev_chunks = chunks_export[chunks_export['Developer'] == developer].copy()
            dev_chunks = dev_chunks.sort_values('Start')
            dev_chunks_export = dev_chunks.drop('Developer', axis=1)
            sheet_name = developer.split('@')[0][:31]
            dev_chunks_export.to_excel(writer, sheet_name=sheet_name, index=False)

        # Metadata tab
        metadata = pd.DataFrame({
            'Metric': [
                'Total Developers',
                'Total Chunks',
                'Total Logs',
                'Total Hours',
                'Inactivity Period (min)',
                'Generated At'
            ],
            'Value': [
                chunks_df['Developer'].nunique(),
                len(chunks_df),
                chunks_df['Log Count'].sum(),
                f"{chunks_df['Duration (hours)'].sum():.2f}",
                inactivity_minutes,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
        })
        metadata.to_excel(writer, sheet_name='Info', index=False)

    output.seek(0)
    return output


def main():
    st.set_page_config(
        page_title="Developer Work Time Analysis",
        page_icon="📊",
        layout="wide"
    )

    st.title("📊 Developer Work Time Analysis")
    st.markdown("Analyze activity logs and generate work time reports")

    # Sidebar configuration
    st.sidebar.header("⚙️ Configuration")

    inactivity_minutes = st.sidebar.slider(
        "Inactivity Threshold (minutes)",
        min_value=5,
        max_value=120,
        value=30,
        step=5,
        help="Minutes of inactivity to consider a new work session"
    )

    min_hours_filter = st.sidebar.number_input(
        "Minimum Hours Filter",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.5,
        help="Filter out developers with total hours below this threshold (0 = no filter)"
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📁 Upload Files")
    st.sidebar.markdown("Upload one or more log files (.txt or .csv)")

    # File uploader
    uploaded_files = st.sidebar.file_uploader(
        "Choose log files",
        type=['txt', 'csv'],
        accept_multiple_files=True,
        help="Upload activity log files in TSV format"
    )

    # Main content
    if not uploaded_files:
        st.info("👆 Please upload one or more log files to begin analysis")

        st.markdown("### 📖 How to use:")
        st.markdown("""
        1. **Upload log files** using the sidebar
        2. **Adjust the inactivity threshold** if needed (default: 30 minutes)
        3. **View the analysis** below
        4. **Download the Excel report** with all details

        ### 📋 What you'll get:
        - **Overall summary** of total hours worked
        - **Summary by developer** with hours, chunks, and log counts
        - **Pivot table** showing hours worked per day per developer
        - **Detailed Excel report** with multiple tabs
        - **Visual charts** of work distribution
        """)
        return

    # Process files
    with st.spinner("Loading files..."):
        df = load_uploaded_logs(uploaded_files)

    if df is None:
        st.error("Failed to load files. Please check the file format.")
        return

    # Process work chunks
    with st.spinner("Processing work chunks..."):
        chunks_df = process_work_chunks(df, inactivity_minutes)

        # Apply minimum hours filter if set
        if min_hours_filter > 0:
            # Calculate total hours per developer
            dev_hours = chunks_df.groupby('Developer')['Duration (hours)'].sum()
            # Get developers that meet the threshold
            valid_developers = dev_hours[dev_hours >= min_hours_filter].index
            # Filter chunks to only include valid developers
            chunks_df_original = chunks_df.copy()
            chunks_df = chunks_df[chunks_df['Developer'].isin(valid_developers)]

            # Show info about filtered developers
            filtered_count = chunks_df_original['Developer'].nunique() - chunks_df['Developer'].nunique()
            if filtered_count > 0:
                st.info(f"🔍 Filtered out {filtered_count} developer(s) with less than {min_hours_filter}h")

        summary_df = generate_summary(chunks_df)

    # Display results
    st.success(f"✅ Analysis complete! Found {len(chunks_df)} work chunks")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Developers", chunks_df['Developer'].nunique())

    with col2:
        st.metric("Total Work Chunks", len(chunks_df))

    with col3:
        st.metric("Total Hours", f"{chunks_df['Duration (hours)'].sum():.2f}h")

    with col4:
        st.metric("Total Logs", f"{chunks_df['Log Count'].sum():,}")

    # Summary by Developer
    st.markdown("### 👥 Summary by Developer")

    # Format summary for display
    summary_display = summary_df.copy()
    summary_display['Duration (hours)'] = summary_display['Duration (hours)'].apply(lambda x: f"{x:.2f}h")
    summary_display['Log Count'] = summary_display['Log Count'].apply(lambda x: f"{x:,.0f}")
    summary_display['Chunk Count'] = summary_display['Chunk Count'].apply(lambda x: f"{x:.0f}")

    st.dataframe(summary_display, use_container_width=True)

    # Charts
    st.markdown("### 📈 Work Distribution")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Hours by Developer")
        chart_data = summary_df.copy()
        chart_data = chart_data.sort_values('Duration (hours)', ascending=True)
        st.bar_chart(chart_data['Duration (hours)'])

    with col2:
        st.markdown("#### Chunks by Developer")
        chart_data = summary_df.copy()
        chart_data = chart_data.sort_values('Chunk Count', ascending=True)
        st.bar_chart(chart_data['Chunk Count'])

    # Pivot by Day
    st.markdown("### 📅 Work Hours by Day")

    chunks_with_date = chunks_df.copy()
    chunks_with_date['Date'] = chunks_with_date['Start'].dt.date

    pivot_by_day = chunks_with_date.groupby(['Date', 'Developer']).agg({
        'Duration (hours)': 'sum'
    }).reset_index()

    pivot_table = pivot_by_day.pivot_table(
        index='Date',
        columns='Developer',
        values='Duration (hours)',
        aggfunc='sum',
        fill_value=0
    ).round(2)

    st.dataframe(pivot_table, use_container_width=True)

    # Timeline chart
    st.markdown("### 📊 Work Timeline (Daily)")
    st.line_chart(pivot_table)

    # Pivot by Week
    st.markdown("### 📅 Work Hours by Week")

    chunks_with_week = chunks_df.copy()
    # Create week number (ISO week format: YYYY-WW)
    chunks_with_week['Week'] = chunks_with_week['Start'].dt.strftime('%Y-W%U')
    chunks_with_week['Week_Start'] = chunks_with_week['Start'].dt.to_period('W').dt.start_time

    pivot_by_week = chunks_with_week.groupby(['Week', 'Week_Start', 'Developer']).agg({
        'Duration (hours)': 'sum'
    }).reset_index()

    pivot_table_week = pivot_by_week.pivot_table(
        index=['Week', 'Week_Start'],
        columns='Developer',
        values='Duration (hours)',
        aggfunc='sum',
        fill_value=0
    ).round(2)

    # Format index to show week start date
    pivot_table_week.index = pivot_table_week.index.get_level_values('Week_Start').strftime('%Y-%m-%d')

    st.dataframe(pivot_table_week, use_container_width=True)

    # Weekly timeline chart
    st.markdown("### 📊 Work Timeline (Weekly)")
    st.line_chart(pivot_table_week)

    # Detailed chunks
    with st.expander("🔍 View All Work Chunks"):
        chunks_display = chunks_df.copy()
        chunks_display['Start'] = chunks_display['Start'].dt.strftime('%Y-%m-%d %H:%M:%S')
        chunks_display['End'] = chunks_display['End'].dt.strftime('%Y-%m-%d %H:%M:%S')
        chunks_display['Duration (hours)'] = chunks_display['Duration (hours)'].apply(lambda x: f"{x:.2f}h")
        chunks_display = chunks_display.round(2)

        st.dataframe(
            chunks_display,
            use_container_width=True,
            hide_index=True
        )

    # Download Excel
    st.markdown("### 💾 Download Report")

    excel_file = create_excel_download(chunks_df, summary_df, inactivity_minutes)

    st.download_button(
        label="📥 Download Excel Report",
        data=excel_file,
        file_name=f"work_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    # Footer
    st.markdown("---")
    st.markdown("Made with ❤️ using Streamlit")


if __name__ == "__main__":
    main()
