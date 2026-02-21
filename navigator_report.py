"""
Navigator report script.
Reads data from Google Sheets into DataFrames for analysis.
"""
from datetime import date

import pandas as pd
from data_cleaner import get_sheets_client, read_sheet_data, write_sheet_data

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
    return reporting_df


def add_rent_metrics(reporting_df, rent_metrics_df):
    """Add rent payment metrics to each reporting week row.

    For each row, looks up rent data for the month the reporting week falls in
    ("this month") and the prior month ("last month").  Produces four columns:
      - rent_this_month          (Yes/No or null)
      - rent_this_month_on_time  (Yes/No or null)
      - rent_last_month          (Yes/No or null)
      - rent_last_month_on_time  (Yes/No or null)

    Caveat: if today is before the 6th and the lookup month equals the current
    calendar month, the metric is set to null (not enough time to determine).
    """
    today = date.today()
    current_month_key = f"{today.month:02d}/{today.year}"
    before_sixth = today.day < 6

    # Build a lookup: (ClientID, "MM/YYYY") -> {rent_paid, rent_paid_on_time}
    rent_lookup = {}
    for _, r in rent_metrics_df.iterrows():
        key = (str(r["ClientID"]), str(r["Month"]))
        rent_lookup[key] = {
            "rent_paid": str(r["rent_paid"]).strip(),
            "rent_paid_on_time": str(r["rent_paid_on_time"]).strip(),
        }

    this_month_col = []
    this_month_ot_col = []
    last_month_col = []
    last_month_ot_col = []

    for _, row in reporting_df.iterrows():
        client_id = str(row["ClientID"])
        week_start = row["reporting_week_start"]

        # "this month" = the month the reporting week falls in
        this_month_key = f"{week_start.month:02d}/{week_start.year}"

        # "last month" = the calendar month before this_month
        if week_start.month == 1:
            last_month_key = f"12/{week_start.year - 1}"
        else:
            last_month_key = f"{week_start.month - 1:02d}/{week_start.year}"

        # --- this month ---
        if before_sixth and this_month_key == current_month_key:
            this_month_col.append(None)
            this_month_ot_col.append(None)
        else:
            info = rent_lookup.get((client_id, this_month_key))
            if info:
                paid = info["rent_paid"] == "Yes"
                this_month_col.append("Yes" if paid else "No")
                this_month_ot_col.append(
                    "Yes" if paid and info["rent_paid_on_time"] == "Yes" else "No"
                )
            else:
                this_month_col.append(None)
                this_month_ot_col.append(None)

        # --- last month ---
        # Null if the resident moved in during the same month as the reporting week
        move_in = row["moveInDate"]
        moved_in_this_month = (
            pd.notna(move_in)
            and move_in.month == week_start.month
            and move_in.year == week_start.year
        )
        if moved_in_this_month:
            last_month_col.append(None)
            last_month_ot_col.append(None)
        else:
            info = rent_lookup.get((client_id, last_month_key))
            if info:
                paid = info["rent_paid"] == "Yes"
                last_month_col.append("Yes" if paid else "No")
                last_month_ot_col.append(
                    "Yes" if paid and info["rent_paid_on_time"] == "Yes" else "No"
                )
            else:
                last_month_col.append(None)
                last_month_ot_col.append(None)

    reporting_df["rent_this_month"] = this_month_col
    reporting_df["rent_this_month_on_time"] = this_month_ot_col
    reporting_df["rent_last_month"] = last_month_col
    reporting_df["rent_last_month_on_time"] = last_month_ot_col

    print(f"  Added rent metrics: {reporting_df.shape}")
    return reporting_df


def add_life_skills_metrics(reporting_df, treatment_thread_df):
    """Add life-skills metrics from Navigator Weekly Survey responses.

    Appends three columns:
      - pursuing_DL          (N/A / Yes / No / No Data Provided)
      - has_budget           (Yes / No / No Data Provided)
      - has_checking_account (Yes / No / No Data Provided)

    Responses are slotted into reporting weeks by their Date. If multiple
    responses exist for the same client/code/week, the latest one wins.
    """
    LIFE_SKILLS_CODES = {
        "drivers-license-detailed",
        "budget-detailed",
        "has-checking-account",
    }

    # Filter to Navigator Weekly Survey and the three codes
    filtered = treatment_thread_df[
        (treatment_thread_df["Document"] == "Navigator Weekly Survey")
        & (treatment_thread_df["Code"].isin(LIFE_SKILLS_CODES))
    ].copy()

    # Parse Date and compute the Monday-starting reporting week
    filtered["Date"] = pd.to_datetime(filtered["Date"], errors="coerce")
    filtered = filtered.dropna(subset=["Date"])
    # Monday of the week the response falls in
    filtered["response_week"] = filtered["Date"] - pd.to_timedelta(
        filtered["Date"].dt.weekday, unit="D"
    )

    # Keep only the latest response per (ClientID, Code, week)
    filtered = filtered.sort_values("Date")
    filtered = filtered.drop_duplicates(
        subset=["ClientID", "Code", "response_week"], keep="last"
    )

    # Build lookup: (ClientID, Code, response_week) -> Value
    response_lookup = {}
    for _, r in filtered.iterrows():
        key = (str(r["ClientID"]), r["Code"], r["response_week"])
        response_lookup[key] = str(r["Value"]).strip()

    pursuing_dl_col = []
    has_budget_col = []
    has_checking_col = []

    for _, row in reporting_df.iterrows():
        client_id = str(row["ClientID"])
        week = row["reporting_week_start"]

        # --- pursuing_DL ---
        # Values: "Yes" / "No and is not pursuing a DL" / "No but is currently pursuing a DL"
        val = response_lookup.get((client_id, "drivers-license-detailed", week))
        if val is None:
            pursuing_dl_col.append("No Data Provided")
        elif val == "Yes":
            pursuing_dl_col.append("N/A")
        elif val == "No but is currently pursuing a DL":
            pursuing_dl_col.append("Yes")
        else:
            pursuing_dl_col.append("No")

        # --- has_budget ---
        val = response_lookup.get((client_id, "budget-detailed", week))
        if val is None:
            has_budget_col.append("No Data Provided")
        elif val == "Yes":
            has_budget_col.append("Yes")
        else:
            has_budget_col.append("No")

        # --- has_checking_account ---
        val = response_lookup.get((client_id, "has-checking-account", week))
        if val is None:
            has_checking_col.append("No Data Provided")
        elif val == "Yes":
            has_checking_col.append("Yes")
        else:
            has_checking_col.append("No")

    reporting_df["pursuing_DL"] = pursuing_dl_col
    reporting_df["has_budget"] = has_budget_col
    reporting_df["has_checking_account"] = has_checking_col

    print(f"  Added life skills metrics: {reporting_df.shape}")
    return reporting_df


def export_reporting_frame(reporting_df):
    """Export the reporting DataFrame to the Navigator Assignment Google Sheet."""
    client = get_sheets_client()

    # Convert DataFrame to list-of-lists with header row
    # Replace NaT/NaN with empty string for clean export
    export_df = reporting_df.copy()
    export_df["reporting_week_start"] = export_df["reporting_week_start"].dt.strftime("%m/%d/%Y")
    export_df["moveInDate"] = export_df["moveInDate"].dt.strftime("%m/%d/%Y")
    export_df = export_df.fillna("")

    data = [export_df.columns.tolist()] + export_df.values.tolist()
    write_sheet_data(client, NAVIGATOR_ASSIGNMENT_SHEET_ID, "result", data)


if __name__ == "__main__":
    nav_assignment_df, treatment_thread_df, resident_info_df, rent_metrics_df, attendance_df = load_data()
    reporting_df = build_reporting_frame(nav_assignment_df, resident_info_df)
    reporting_df = add_rent_metrics(reporting_df, rent_metrics_df)
    reporting_df = add_life_skills_metrics(reporting_df, treatment_thread_df)
    export_reporting_frame(reporting_df)
