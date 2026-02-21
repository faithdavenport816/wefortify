"""
Navigator report script.
Reads data from Google Sheets into DataFrames for analysis.
"""
from datetime import date

import pandas as pd
from data_cleaner import get_sheets_client, read_sheet_data

REPORTING_START = pd.Timestamp("2026-01-05")  # first Monday


# Sheet IDs
NAVIGATOR_ASSIGNMENT_SHEET_ID = "1Qiox1LKdLOrIFFdmL9Ee9qFbm818yvrlomaRZSwwVFo"
DATA_PROCESSING_SHEET = "196rg3YfpssRLsdFig4yN9G3U9NrQFPEeROnr1oSNGCA"


def load_data():
    """Read all required tabs from Google Sheets into DataFrames."""
    client = get_sheets_client()

    # From Navigator sheet
    nav_assignment_data = read_sheet_data(client, NAVIGATOR_ASSIGNMENT_SHEET_ID, "Navigator x Resident Assignment")
    nav_assignment_df = pd.DataFrame(nav_assignment_data[1:], columns=nav_assignment_data[0])

    treatment_thread_data = read_sheet_data(client, DATA_PROCESSING_SHEET, "fake_treatment_thread_export")
    treatment_thread_df = pd.DataFrame(treatment_thread_data[1:], columns=treatment_thread_data[0])

    # From Export sheet
    resident_info_data = read_sheet_data(client, DATA_PROCESSING_SHEET, "resident_info_frame")
    resident_info_df = pd.DataFrame(resident_info_data[1:], columns=resident_info_data[0])

    rent_metrics_data = read_sheet_data(client, DATA_PROCESSING_SHEET, "rent_metrics_frame")
    rent_metrics_df = pd.DataFrame(rent_metrics_data[1:], columns=rent_metrics_data[0])

    attendance_data = read_sheet_data(client, DATA_PROCESSING_SHEET, "attendance_frame")
    attendance_df = pd.DataFrame(attendance_data[1:], columns=attendance_data[0])

    print(f"\nLoaded all DataFrames:")
    print(f"  nav_assignment_df:  {nav_assignment_df.shape}")
    print(f"  treatment_thread_df:  {treatment_thread_df.shape}")
    print(f"  resident_info_df:   {resident_info_df.shape}")
    print(f"  rent_metrics_df:    {rent_metrics_df.shape}")
    print(f"  attendance_df:      {attendance_df.shape}")

    return nav_assignment_df, treatment_thread_df, resident_info_df, rent_metrics_df, attendance_df


def build_reporting_frame(nav_assignment_df, resident_info_df):
    """Create one row per (ClientID, Navigator, reporting_week_start).

    Expands navigator assignments into weekly reporting rows, bounded by
    the navigator assignment period and the resident's moveout date (if any).
    """
    today = pd.Timestamp(date.today())

    # Parse dates in nav_assignment_df
    for col in ["moveInDate (for reference)", "NavigatorStartDate", "NavigatorEndDate"]:
        nav_assignment_df[col] = pd.to_datetime(nav_assignment_df[col], errors="coerce")

    # Parse moveout-date in resident_info_df and keep only what we need
    resident_info_df = resident_info_df[["ClientID", "moveout-date"]].copy()
    resident_info_df["moveout-date"] = pd.to_datetime(resident_info_df["moveout-date"], errors="coerce")

    # Join to get moveout-date onto nav assignments
    merged = nav_assignment_df.merge(resident_info_df, on="ClientID", how="left")

    rows = []
    for _, r in merged.iterrows():
        nav_start = r["NavigatorStartDate"]
        nav_end = r["NavigatorEndDate"]

        # Skip rows without a valid navigator start date
        if pd.isna(nav_start):
            continue

        # Reporting end = min(today, moveout-date) — ignore NaT moveout
        reporting_end = today
        if pd.notna(r["moveout-date"]):
            reporting_end = min(today, r["moveout-date"])

        # Also cap at navigator end date if present
        if pd.notna(nav_end):
            reporting_end = min(reporting_end, nav_end)

        # Generate Monday-starting weeks from REPORTING_START through reporting_end
        if reporting_end < REPORTING_START:
            continue

        weeks = pd.date_range(start=REPORTING_START, end=reporting_end, freq="W-MON")

        # Only keep weeks that overlap with the navigator assignment period
        weeks = [w for w in weeks if w >= nav_start]

        for w in weeks:
            rows.append({
                "ClientID": r["ClientID"],
                "FirstName": r["FirstName"],
                "LastName": r["LastName"],
                "moveInDate": r["moveInDate (for reference)"],
                "Navigator": r["Navigator"],
                "NavigatorCode": r["NavigatorCode"],
                "reporting_week_start": w,
            })

    reporting_df = pd.DataFrame(rows)
    print(f"  reporting_df:       {reporting_df.shape}")
    print(reporting_df)
    return reporting_df


if __name__ == "__main__":
    nav_assignment_df, treatment_thread_df, resident_info_df, rent_metrics_df, attendance_df = load_data()
    reporting_df = build_reporting_frame(nav_assignment_df, resident_info_df)
