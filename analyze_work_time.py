#!/usr/bin/env python3
"""
Script para analisar tempo de trabalho de desenvolvedores em modelos.
Agrupa logs em chunks baseado em períodos de inatividade.
"""

import pandas as pd
from datetime import datetime, timedelta
import argparse
import sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils.dataframe import dataframe_to_rows


def parse_arguments():
    """Parse argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description='Analisa tempo de trabalho de desenvolvedores baseado em logs de atividade.'
    )
    parser.add_argument(
        'input_files',
        type=str,
        nargs='*',  # Torna opcional (0 ou mais)
        help='Caminho(s) para o(s) arquivo(s) de log (formato CSV/TSV). Se não especificado, usa pasta logs/'
    )
    parser.add_argument(
        '--logs-dir',
        type=str,
        default='logs',
        help='Pasta contendo arquivos de log (padrão: logs/). Usado quando input_files não é fornecido.'
    )
    parser.add_argument(
        '-i', '--inactivity',
        type=int,
        default=30,
        help='Período de inatividade em minutos para considerar novo chunk (padrão: 30)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Arquivo de saída para o relatório (padrão: exibe no terminal)'
    )
    parser.add_argument(
        '--csv',
        action='store_true',
        help='Exportar relatório também em formato CSV'
    )
    parser.add_argument(
        '--excel',
        type=str,
        default=None,
        help='Exportar relatório em formato Excel com múltiplas abas'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Exibir apenas resumo por desenvolvedor'
    )
    parser.add_argument(
        '--min-hours',
        type=float,
        default=0.0,
        help='Filter out developers with total hours below this threshold (default: 0 = no filter)'
    )

    return parser.parse_args()


def find_log_files(logs_dir):
    """
    Automatically searches for .txt and .csv files in a folder.

    Args:
        logs_dir: Path to the folder containing logs

    Returns:
        List of file paths found
    """
    logs_path = Path(logs_dir)

    if not logs_path.exists():
        print(f"❌ Folder not found: {logs_dir}")
        sys.exit(1)

    if not logs_path.is_dir():
        print(f"❌ Path is not a folder: {logs_dir}")
        sys.exit(1)

    # Search for .txt and .csv files
    txt_files = list(logs_path.glob('*.txt'))
    csv_files = list(logs_path.glob('*.csv'))

    all_files = txt_files + csv_files

    if not all_files:
        print(f"❌ No .txt or .csv files found in: {logs_dir}")
        sys.exit(1)

    # Convert to strings
    all_files = [str(f) for f in all_files]
    all_files.sort()  # Sort alphabetically

    print(f"🔍 Found {len(all_files)} file(s) in {logs_dir}:")
    for f in all_files:
        print(f"   - {Path(f).name}")
    print()

    return all_files


def load_logs(file_paths):
    """
    Loads one or multiple log files.

    Args:
        file_paths: List of file paths or string with a single file

    Returns:
        Combined DataFrame with all logs
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    all_dfs = []

    for file_path in file_paths:
        print(f"📁 Loading file: {file_path}")

        try:
            # Try to read as TSV (tab-separated)
            df = pd.read_csv(file_path, sep='\t', encoding='utf-8', low_memory=False)
            df['_source_file'] = Path(file_path).name  # Add column with file name
            all_dfs.append(df)
            print(f"✓ File loaded: {len(df)} logs found")
        except Exception as e:
            print(f"❌ Error loading file {file_path}: {e}")
            sys.exit(1)

    # Combine all DataFrames
    if len(all_dfs) > 1:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        print(f"\n📊 Combined total: {len(combined_df)} logs from {len(file_paths)} file(s)")
    else:
        combined_df = all_dfs[0]

    return combined_df


def process_work_chunks(df, inactivity_minutes=30):
    """
    Processes logs and groups them into work chunks.

    Args:
        df: DataFrame with logs
        inactivity_minutes: Minutes of inactivity to consider a new chunk

    Returns:
        DataFrame with work chunks
    """
    print(f"\n⚙️  Processing work chunks (inactivity threshold: {inactivity_minutes} minutes)...")

    # Convert date/time column to datetime
    df['DateTime'] = pd.to_datetime(df['Date/Time (UTC)'], format='%Y-%m-%d %H:%M:%S')

    # Filter only records with valid user
    df = df[df['User'].notna() & (df['User'] != '')]

    # Sort by user and date/time
    df = df.sort_values(['User', 'DateTime'])

    chunks = []
    inactivity_threshold = timedelta(minutes=inactivity_minutes)

    # Group by user
    for user, user_logs in df.groupby('User'):
        user_logs = user_logs.reset_index(drop=True)

        chunk_start = None
        chunk_end = None
        chunk_logs_count = 0

        for idx, row in user_logs.iterrows():
            current_time = row['DateTime']

            # First log of user or start of new chunk
            if chunk_start is None:
                chunk_start = current_time
                chunk_end = current_time
                chunk_logs_count = 1
            else:
                time_diff = current_time - chunk_end

                # If difference > threshold, close current chunk and start new one
                if time_diff > inactivity_threshold:
                    # Save previous chunk
                    duration = chunk_end - chunk_start
                    chunks.append({
                        'Developer': user,
                        'Start': chunk_start,
                        'End': chunk_end,
                        'Duration (min)': duration.total_seconds() / 60,
                        'Duration (hours)': duration.total_seconds() / 3600,
                        'Log Count': chunk_logs_count,
                        'Gap to Next': time_diff.total_seconds() / 60
                    })

                    # Start new chunk
                    chunk_start = current_time
                    chunk_end = current_time
                    chunk_logs_count = 1
                else:
                    # Continue in same chunk
                    chunk_end = current_time
                    chunk_logs_count += 1

        # Save last chunk of user
        if chunk_start is not None:
            duration = chunk_end - chunk_start
            chunks.append({
                'Developer': user,
                'Start': chunk_start,
                'End': chunk_end,
                'Duration (min)': duration.total_seconds() / 60,
                'Duration (hours)': duration.total_seconds() / 3600,
                'Log Count': chunk_logs_count,
                'Gap to Next': None
            })

    chunks_df = pd.DataFrame(chunks)
    print(f"✓ {len(chunks_df)} work chunks identified")

    return chunks_df


def generate_summary(chunks_df):
    """Generates summary by developer."""
    summary = chunks_df.groupby('Developer').agg({
        'Duration (hours)': 'sum',
        'Log Count': 'sum',
        'Start': 'count'  # Count number of chunks
    }).rename(columns={'Start': 'Chunk Count'})

    summary = summary.round(2)
    summary = summary.sort_values('Duration (hours)', ascending=False)

    return summary


def format_timedelta(td):
    """Formats timedelta to readable string."""
    if pd.isna(td):
        return ''
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}h {minutes}min"


def generate_report(chunks_df, summary_only=False):
    """Generates formatted report."""
    report_lines = []

    report_lines.append("=" * 100)
    report_lines.append("📊 DEVELOPER WORK TIME REPORT")
    report_lines.append("=" * 100)
    report_lines.append("")

    # General summary
    total_developers = chunks_df['Developer'].nunique()
    total_chunks = len(chunks_df)
    total_hours = chunks_df['Duration (hours)'].sum()

    report_lines.append("📈 OVERALL SUMMARY")
    report_lines.append("-" * 100)
    report_lines.append(f"Total developers: {total_developers}")
    report_lines.append(f"Total work chunks: {total_chunks}")
    report_lines.append(f"Total hours worked: {total_hours:.2f}h")
    report_lines.append("")

    # Summary by developer
    summary = generate_summary(chunks_df)

    report_lines.append("👥 SUMMARY BY DEVELOPER")
    report_lines.append("-" * 100)
    report_lines.append(f"{'Developer':<50} {'Hours':>12} {'Chunks':>10} {'Logs':>10}")
    report_lines.append("-" * 100)

    for dev, row in summary.iterrows():
        report_lines.append(
            f"{dev:<50} {row['Duration (hours)']:>11.2f}h {row['Chunk Count']:>10.0f} {row['Log Count']:>10.0f}"
        )

    report_lines.append("")

    # Chunk details (if not summary only)
    if not summary_only:
        report_lines.append("📋 WORK CHUNK DETAILS")
        report_lines.append("=" * 100)

        for developer in chunks_df['Developer'].unique():
            dev_chunks = chunks_df[chunks_df['Developer'] == developer].copy()
            dev_chunks = dev_chunks.sort_values('Start')

            report_lines.append("")
            report_lines.append(f"👤 {developer}")
            report_lines.append("-" * 100)
            report_lines.append(
                f"{'#':<5} {'Start':<20} {'End':<20} {'Duration':>15} {'Logs':>8} {'Gap':>15}"
            )
            report_lines.append("-" * 100)

            for idx, (_, chunk) in enumerate(dev_chunks.iterrows(), 1):
                start = chunk['Start'].strftime('%Y-%m-%d %H:%M:%S')
                end = chunk['End'].strftime('%Y-%m-%d %H:%M:%S')
                duration = f"{chunk['Duration (hours)']:.2f}h"
                logs = int(chunk['Log Count'])
                gap = f"{chunk['Gap to Next']:.0f}min" if pd.notna(chunk['Gap to Next']) else '-'

                report_lines.append(
                    f"{idx:<5} {start:<20} {end:<20} {duration:>15} {logs:>8} {gap:>15}"
                )

            total_dev_hours = dev_chunks['Duration (hours)'].sum()
            total_dev_chunks = len(dev_chunks)
            report_lines.append("-" * 100)
            report_lines.append(f"Total: {total_dev_hours:.2f}h in {total_dev_chunks} chunks")

    report_lines.append("")
    report_lines.append("=" * 100)

    return "\n".join(report_lines)


def export_excel(chunks_df, summary_df, output_file, inactivity_minutes=30):
    """
    Exports reports to Excel with multiple tabs.

    Args:
        chunks_df: DataFrame with work chunks
        summary_df: DataFrame with summary by developer
        output_file: Path to Excel output file
        inactivity_minutes: Minutes of inactivity used in processing
    """
    print(f"\n📊 Exporting to Excel: {output_file}")

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
        'Start': 'count'  # Count chunks
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

    # Add total by row (total by day)
    pivot_table['TOTAL'] = pivot_table.sum(axis=1).round(2)

    # Add total by column (total by developer)
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
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Tab 1: Summary
        summary_df.to_excel(writer, sheet_name='Summary', index=True)

        # Tab 2: Pivot by Day
        pivot_table.to_excel(writer, sheet_name='Pivot - Hours by Day', index=True)

        # Tab 3: Pivot by Week
        pivot_table_week.to_excel(writer, sheet_name='Pivot - Hours by Week', index=True)

        # Tab 4: Details by Day (list)
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

            # Remove developer column (already in tab name)
            dev_chunks_export = dev_chunks.drop('Developer', axis=1)

            # Tab name (truncate if needed - Excel has 31 character limit)
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

    print(f"✓ Excel exported with {7 + chunks_df['Developer'].nunique()} tabs")
    print(f"  - Summary")
    print(f"  - Pivot - Hours by Day")
    print(f"  - Pivot - Hours by Week")
    print(f"  - Work by Day")
    print(f"  - Work by Week")
    print(f"  - All Chunks")
    for dev in chunks_df['Developer'].unique():
        print(f"  - {dev.split('@')[0]}")
    print(f"  - Info")


def export_csv(chunks_df, summary_df, base_filename):
    """Exports reports to CSV."""
    # Detailed chunks
    chunks_file = base_filename.replace('.txt', '_chunks.csv')
    chunks_export = chunks_df.copy()
    chunks_export['Start'] = chunks_export['Start'].dt.strftime('%Y-%m-%d %H:%M:%S')
    chunks_export['End'] = chunks_export['End'].dt.strftime('%Y-%m-%d %H:%M:%S')
    chunks_export.to_csv(chunks_file, index=False, encoding='utf-8')
    print(f"✓ Chunks exported: {chunks_file}")

    # Summary
    summary_file = base_filename.replace('.txt', '_summary.csv')
    summary_df.to_csv(summary_file, encoding='utf-8')
    print(f"✓ Summary exported: {summary_file}")


def main():
    """Main function."""
    args = parse_arguments()

    # Determine which files to process
    if args.input_files:
        # Use specified files
        files_to_process = args.input_files
    else:
        # Automatically search in logs/ folder
        files_to_process = find_log_files(args.logs_dir)

    # Load logs (one or multiple files)
    df = load_logs(files_to_process)

    # Process chunks
    chunks_df = process_work_chunks(df, args.inactivity)

    # Apply minimum hours filter if set
    if args.min_hours > 0:
        # Calculate total hours per developer
        dev_hours = chunks_df.groupby('Developer')['Duration (hours)'].sum()
        # Get developers that meet the threshold
        valid_developers = dev_hours[dev_hours >= args.min_hours].index
        # Filter chunks to only include valid developers
        chunks_df_original = chunks_df.copy()
        chunks_df = chunks_df[chunks_df['Developer'].isin(valid_developers)]

        # Show info about filtered developers
        filtered_count = chunks_df_original['Developer'].nunique() - chunks_df['Developer'].nunique()
        if filtered_count > 0:
            print(f"\n🔍 Filtered out {filtered_count} developer(s) with less than {args.min_hours}h")

    # Generate report
    report = generate_report(chunks_df, args.summary)

    # Display or save report
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report, encoding='utf-8')
        print(f"\n✓ Report saved to: {args.output}")
    else:
        print("\n" + report)

    # Generate summary for export
    summary = generate_summary(chunks_df)

    # Export CSV if requested
    if args.csv:
        export_csv(chunks_df, summary, files_to_process[0])

    # Export Excel if requested
    if args.excel:
        export_excel(chunks_df, summary, args.excel, args.inactivity)

    print("\n✅ Processing complete!")


if __name__ == '__main__':
    main()
