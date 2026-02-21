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


def _read_sheet_as_df(client, sheet_id, tab_name):
    """Read a Google Sheet tab and return it as a DataFrame."""
    data = read_sheet_data(client, sheet_id, tab_name)
    return pd.DataFrame(data[1:], columns=data[0])


def load_data():
    """Read all required tabs from Google Sheets into DataFrames."""
    client = get_sheets_client()

    # From Navigator sheet
    nav_assignment_df = _read_sheet_as_df(client, NAVIGATOR_ASSIGNMENT_SHEET_ID, "Navigator x Resident Assignment")
    treatment_thread_df = _read_sheet_as_df(client, DATA_PROCESSING_SHEET, "fake_treatment_thread_export")

    # From Export sheet
    resident_info_df = _read_sheet_as_df(client, DATA_PROCESSING_SHEET, "resident_info_frame")
    rent_metrics_df = _read_sheet_as_df(client, DATA_PROCESSING_SHEET, "rent_metrics_frame")
    attendance_df = _read_sheet_as_df(client, DATA_PROCESSING_SHEET, "fake_attendance_frame")

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
      - rent_last_month          (Yes/No, N/A if not resident prior month, or null)
      - rent_last_month_on_time  (Yes/No, N/A if not resident prior month, or null)

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
            last_month_col.append("N/A")
            last_month_ot_col.append("N/A")
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


def _build_survey_lookup(treatment_thread_df, codes):
    """Build a lookup dict from Navigator Weekly Survey responses.

    Filters to "Navigator Weekly Survey" rows matching the given codes,
    parses dates, computes the Monday-based reporting week, deduplicates
    (keeping the latest response per client/code/week), and returns a dict
    mapping (ClientID, Code, response_week) -> Value.
    """
    filtered = treatment_thread_df[
        (treatment_thread_df["Document"] == "Navigator Weekly Survey")
        & (treatment_thread_df["Code"].isin(codes))
    ].copy()

    filtered["Date"] = pd.to_datetime(filtered["Date"], errors="coerce")
    filtered = filtered.dropna(subset=["Date"])
    filtered["response_week"] = filtered["Date"] - pd.to_timedelta(
        filtered["Date"].dt.weekday, unit="D"
    )

    filtered = filtered.sort_values("Date")
    filtered = filtered.drop_duplicates(
        subset=["ClientID", "Code", "response_week"], keep="last"
    )

    lookup = {}
    for _, r in filtered.iterrows():
        key = (str(r["ClientID"]), r["Code"], r["response_week"])
        lookup[key] = str(r["Value"]).strip()
    return lookup


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

    response_lookup = _build_survey_lookup(treatment_thread_df, LIFE_SKILLS_CODES)

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


def add_career_metrics(reporting_df, treatment_thread_df):
    """Add career metrics from Navigator Weekly Survey responses.

    Appends five columns:
      - pursuing_GED          (N/A / Yes / No / No Data Provided)
      - edu_status            (raw value of enroll-education / No Data Provided)
      - employed              (Yes / No / No Data Provided)
      - employed_living_wage  (Yes / No / No Data Provided)
      - avg_time_job_searching (raw value of hours-job-searching when unemployed / N/A / No Data Provided)
    """
    CAREER_CODES = {
        "highschool-degree",
        "enroll-education",
        "employment-status-simple",
        "hours-job-searching",
    }

    response_lookup = _build_survey_lookup(treatment_thread_df, CAREER_CODES)

    pursuing_ged_col = []
    edu_status_col = []
    employed_col = []
    employed_lw_col = []
    avg_time_job_searching_col = []

    for _, row in reporting_df.iterrows():
        client_id = str(row["ClientID"])
        week = row["reporting_week_start"]

        hs = response_lookup.get((client_id, "highschool-degree", week))
        enroll = response_lookup.get((client_id, "enroll-education", week))
        emp = response_lookup.get((client_id, "employment-status-simple", week))
        hours_js = response_lookup.get((client_id, "hours-job-searching", week))

        # --- pursuing_GED ---
        if hs is None:
            pursuing_ged_col.append("No Data Provided")
        elif hs == "Yes":
            pursuing_ged_col.append("N/A")
        elif enroll in ("High School Degree", "Pursuing GED"):
            pursuing_ged_col.append("Yes")
        else:
            pursuing_ged_col.append("No")

        # --- edu_status (raw value of enroll-education) ---
        if enroll is None:
            edu_status_col.append("No Data Provided")
        else:
            edu_status_col.append(enroll)

        # --- employed ---
        if emp is None:
            employed_col.append("No Data Provided")
        elif emp in ("Employed at a Living Wage", "Employed at below a Living Wage"):
            employed_col.append("Yes")
        elif emp == "Unemployed":
            employed_col.append("No")
        else:
            employed_col.append("No Data Provided")

        # --- employed_living_wage ---
        if emp is None:
            employed_lw_col.append("No Data Provided")
        elif emp == "Employed at a Living Wage":
            employed_lw_col.append("Yes")
        else:
            employed_lw_col.append("No")

        # --- avg_time_job_searching ---
        if emp is not None and emp != "Unemployed":
            avg_time_job_searching_col.append("N/A")
        elif hours_js is not None:
            avg_time_job_searching_col.append(hours_js)
        else:
            avg_time_job_searching_col.append("No Data Provided")

    reporting_df["pursuing_GED"] = pursuing_ged_col
    reporting_df["edu_status"] = edu_status_col
    reporting_df["employed"] = employed_col
    reporting_df["employed_living_wage"] = employed_lw_col
    reporting_df["avg_time_job_searching"] = avg_time_job_searching_col

    print(f"  Added career metrics: {reporting_df.shape}")
    return reporting_df


def add_empowerment_metric(reporting_df, treatment_thread_df):
    """Add empowerment plan metric from Navigator Weekly Survey responses.

    Appends one column:
      - empowerment_plan  (Yes / No / N/A / No Data Provided)

    Mapping from raw progress-empowerment-plan values:
      Yes: Mixed Progress, Overall Forward Progress,
           Some Forward and Some Backwards, Stayed the Same
      No:  Overall Backwards Progress
      N/A: No Meeting, No history
    """
    YES_VALUES = {
        "Mixed Progress",
        "Overall Forward Progress",
        "Some Forward and Some Backwards",
    }
    NO_VALUES = {"Overall Backwards Progress", "Stayed the Same"}
    NA_VALUES = {"No Meeting", "No history"}

    response_lookup = _build_survey_lookup(
        treatment_thread_df, {"progress-empowerment-plan"}
    )

    empowerment_col = []
    for _, row in reporting_df.iterrows():
        val = response_lookup.get(
            (str(row["ClientID"]), "progress-empowerment-plan", row["reporting_week_start"])
        )
        if val is None:
            empowerment_col.append("No Data Provided")
        elif val in YES_VALUES:
            empowerment_col.append("Yes")
        elif val in NO_VALUES:
            empowerment_col.append("No")
        elif val in NA_VALUES:
            empowerment_col.append("N/A")
        else:
            empowerment_col.append("No Data Provided")

    reporting_df["empowerment_plan"] = empowerment_col

    print(f"  Added empowerment metric: {reporting_df.shape}")
    return reporting_df


def add_one_on_one_metric(reporting_df, attendance_df):
    """Add one-on-one compliance metric based on attendance history.

    Appends one column:
      - one_on_one_compliant  (Yes / No / No Data Provided)

    "Yes" if the resident has fewer than 2 ABSENCE values in their last 5
    one-on-ones prior to the end of the reporting week. "No" if 2 or more
    ABSENCE values. "No Data Provided" if no attendance records exist.
    """
    att = attendance_df.copy()
    att = att[att["Code"] == "Individual Case Management"]
    att["Date"] = pd.to_datetime(att["Date"], errors="coerce")
    att = att.dropna(subset=["Date"])
    att["attendee_status"] = att["attendee_status"].str.strip()
    att = att.sort_values("Date")

    # Group attendance records by ClientID for efficient lookup
    att_by_client = {}
    for _, r in att.iterrows():
        client_id = str(r["ClientID"])
        att_by_client.setdefault(client_id, []).append({
            "date": r["Date"],
            "status": r["attendee_status"],
        })

    compliant_col = []
    for _, row in reporting_df.iterrows():
        client_id = str(row["ClientID"])
        week_end = row["reporting_week_start"] + pd.Timedelta(days=6)

        records = att_by_client.get(client_id)
        if not records:
            compliant_col.append("No Data Provided")
            continue

        # Last 5 meetings on or before the end of this reporting week
        prior = [r for r in records if r["date"] <= week_end]
        if not prior:
            compliant_col.append("No Data Provided")
            continue

        last_five = prior[-5:]
        absences = sum(1 for r in last_five if r["status"] == "ABSENCE")
        compliant_col.append("No" if absences >= 2 else "Yes")

    reporting_df["one_on_one_compliant"] = compliant_col

    print(f"  Added one-on-one metric: {reporting_df.shape}")
    return reporting_df


def add_ra_compliant_metric(reporting_df, attendance_df):
    """Add Resident Association meeting compliance metric.

    Appends one column:
      - ra_compliant  (Yes / No)

    For residents in the village 12+ months: "Yes" if they have attended
    (ATTENDED or EXCUSED) at least 9 RA meetings in the 12 months prior to
    the end of the reporting week.

    For residents in the village < 12 months: "Yes" if the number of RA
    meetings attended is no more than 2 fewer than their months in the village
    (e.g. 8 months → need at least 6 meetings).
    """
    att = attendance_df.copy()
    att = att[att["Code"] == "Resident Association Meeting"]
    att["Date"] = pd.to_datetime(att["Date"], errors="coerce")
    att = att.dropna(subset=["Date"])
    att["attendee_status"] = att["attendee_status"].str.strip()
    # Only count ATTENDED and EXCUSED
    att = att[att["attendee_status"].isin(["ATTENDED", "EXCUSED"])]
    # Deduplicate so the same meeting date isn't counted twice
    att = att.drop_duplicates(subset=["ClientID", "Date"])
    att = att.sort_values("Date")

    # Group by ClientID for efficient lookup
    att_by_client = {}
    for _, r in att.iterrows():
        client_id = str(r["ClientID"])
        att_by_client.setdefault(client_id, []).append(r["Date"])

    ra_col = []
    for _, row in reporting_df.iterrows():
        client_id = str(row["ClientID"])
        move_in = row["moveInDate"]
        week_end = row["reporting_week_start"] + pd.Timedelta(days=6)

        if pd.isna(move_in):
            ra_col.append("No")
            continue

        dates = att_by_client.get(client_id, [])

        # Months the resident has lived in the village as of the reporting week
        months_in_village = (
            (week_end.year - move_in.year) * 12 + (week_end.month - move_in.month)
        )

        if months_in_village < 3:
            ra_col.append("N/A")
        elif months_in_village >= 12:
            # Count RA meetings in the 12 months prior to end of reporting week
            twelve_months_ago = week_end - pd.DateOffset(months=12)
            count = sum(1 for d in dates if twelve_months_ago <= d <= week_end)
            ra_col.append("Yes" if count >= 9 else "No")
        else:
            # Count all RA meetings from move-in through end of reporting week
            count = sum(1 for d in dates if move_in <= d <= week_end)
            required = months_in_village - 2
            ra_col.append("Yes" if count >= required else "No")

    reporting_df["ra_compliant"] = ra_col

    print(f"  Added RA compliant metric: {reporting_df.shape}")
    return reporting_df


def build_navigator_summary(reporting_df):
    """Aggregate metrics to one row per (Navigator, NavigatorCode, reporting_week_start).

    Ratio metrics: count(Yes) / count(Yes, No, No Data Provided).
    N/A and null are excluded from both numerator and denominator.
    """
    RATIO_COLS = [
        "rent_this_month", "rent_this_month_on_time",
        "rent_last_month", "rent_last_month_on_time",
        "pursuing_DL", "has_budget", "has_checking_account",
        "pursuing_GED", "employed", "employed_living_wage",
        "one_on_one_compliant", "ra_compliant",
        "empowerment_plan",
    ]
    VALID_VALUES = {"Yes", "No", "No Data Provided"}

    group_keys = ["Navigator", "NavigatorCode", "reporting_week_start"]
    grouped = reporting_df.groupby(group_keys)

    rows = []
    for key, group in grouped:
        row = dict(zip(group_keys, key))

        for col in RATIO_COLS:
            valid = group[col][group[col].isin(VALID_VALUES)]
            if len(valid) == 0:
                row[col] = None
            else:
                row[col] = (valid == "Yes").sum() / len(valid)

        row["edu_status"] = "N/A"

        # avg_time_job_searching: average of numeric values, skip N/A and No Data Provided
        vals = group["avg_time_job_searching"]
        numeric_vals = []
        for v in vals:
            if v in ("N/A", "No Data Provided", None) or pd.isna(v):
                continue
            try:
                numeric_vals.append(float(v))
            except (ValueError, TypeError):
                continue
        row["avg_time_job_searching"] = (
            sum(numeric_vals) / len(numeric_vals) if numeric_vals else None
        )

        rows.append(row)

    # TOTAL row per week: aggregate across unique residents (dedupe by ClientID)
    for week, week_group in reporting_df.groupby("reporting_week_start"):
        deduped = week_group.drop_duplicates(subset=["ClientID"])
        row = {
            "Navigator": "TOTAL",
            "NavigatorCode": "TOTAL",
            "reporting_week_start": week,
        }

        for col in RATIO_COLS:
            valid = deduped[col][deduped[col].isin(VALID_VALUES)]
            if len(valid) == 0:
                row[col] = None
            else:
                row[col] = (valid == "Yes").sum() / len(valid)

        row["edu_status"] = "N/A"

        vals = deduped["avg_time_job_searching"]
        numeric_vals = []
        for v in vals:
            if v in ("N/A", "No Data Provided", None) or pd.isna(v):
                continue
            try:
                numeric_vals.append(float(v))
            except (ValueError, TypeError):
                continue
        row["avg_time_job_searching"] = (
            sum(numeric_vals) / len(numeric_vals) if numeric_vals else None
        )

        rows.append(row)

    summary_df = pd.DataFrame(rows)
    print(f"  navigator_summary_df: {summary_df.shape}")
    return summary_df


def export_reporting_frame(reporting_df):
    """Export the reporting DataFrame to the Navigator Assignment Google Sheet."""
    client = get_sheets_client()

    # Convert DataFrame to list-of-lists with header row
    # Replace NaT/NaN with empty string for clean export
    export_df = reporting_df.copy()
    export_df["reporting_week_start"] = export_df["reporting_week_start"].dt.strftime("%m/%d/%Y")
    export_df["moveInDate"] = export_df["moveInDate"].dt.strftime("%m/%d/%Y")
    export_df["NavigatorCode"] = "'" + export_df["NavigatorCode"].astype(str)
    export_df = export_df.fillna("")

    data = [export_df.columns.tolist()] + export_df.values.tolist()
    write_sheet_data(client, NAVIGATOR_ASSIGNMENT_SHEET_ID, "resident_metrics", data)


def export_navigator_summary(navigator_summary_df):
    """Export the navigator summary DataFrame to the Navigator Assignment Google Sheet."""
    client = get_sheets_client()

    export_df = navigator_summary_df.copy()
    export_df["reporting_week_start"] = export_df["reporting_week_start"].dt.strftime("%m/%d/%Y")
    export_df["NavigatorCode"] = "'" + export_df["NavigatorCode"].astype(str)
    export_df = export_df.fillna("")

    data = [export_df.columns.tolist()] + export_df.values.tolist()
    write_sheet_data(client, NAVIGATOR_ASSIGNMENT_SHEET_ID, "aggregated_metrics", data)


if __name__ == "__main__":
    nav_assignment_df, treatment_thread_df, resident_info_df, rent_metrics_df, attendance_df = load_data()
    reporting_df = build_reporting_frame(nav_assignment_df, resident_info_df)
    reporting_df = add_rent_metrics(reporting_df, rent_metrics_df)
    reporting_df = add_life_skills_metrics(reporting_df, treatment_thread_df)
    reporting_df = add_career_metrics(reporting_df, treatment_thread_df)
    reporting_df = add_empowerment_metric(reporting_df, treatment_thread_df)
    reporting_df = add_one_on_one_metric(reporting_df, attendance_df)
    reporting_df = add_ra_compliant_metric(reporting_df, attendance_df)
    navigator_summary_df = build_navigator_summary(reporting_df)
    export_reporting_frame(reporting_df)
    export_navigator_summary(navigator_summary_df)
