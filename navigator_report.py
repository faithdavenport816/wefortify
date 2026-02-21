"""
Navigator report script.
Reads data from Google Sheets into DataFrames for analysis.
"""
import pandas as pd
from data_cleaner import get_sheets_client, read_sheet_data


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


if __name__ == "__main__":
    nav_assignment_df, treatment_thread_df, resident_info_df, rent_metrics_df, attendance_df = load_data()
