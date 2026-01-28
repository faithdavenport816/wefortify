"""
Data cleaning and transformation pipeline for ReliaTrax exports.
Processes raw exported data into analytical frames (long, wide, yoy).
"""
import gspread
import os
import json
import platform
from datetime import datetime
from dateutil.relativedelta import relativedelta
from oauth2client.service_account import ServiceAccountCredentials

# Determine the correct date format directive based on platform
if platform.system() == 'Windows':
    DATE_FORMAT = '%#m-%#d-%Y-%H-%M'  # Windows uses #
else:
    DATE_FORMAT = '%-m-%-d-%Y-%H-%M'  # Linux/Mac uses -


# Configuration
SHEET_ID = "196rg3YfpssRLsdFig4yN9G3U9NrQFPEeROnr1oSNGCA"

# Survey Configuration
SS_SURVEY_CODE = 9000
SS_QUESTION_CODES = [
    'emo-mgmt', 'mental-health', 'self-comp', 'budget', 'financial-struct',
    'goals', 'hlth-ins-access', 'house-upkeep', 'time-mgmt', 'transport',
    'understanding-serv', 'food', 'rent-ready', 'legal', 'safety',
    'phys-health', 'sub-use', 'support-sys', 'career-res', 'education',
    'emp-stablility', 'future-hopes', 'income-met'
]

# Aggregation categories for rollups
AGGREGATION_CONFIG = {
    "9000": {
        "Emotional & Mental Health": ["emo-mgmt", "mental-health", "self-comp"],
        "Life Skills": [
            "budget", "financial-struct", "goals", "hlth-ins-access",
            "house-upkeep", "time-mgmt", "transport", "understanding-serv"
        ],
        "Safety & Stability": ["food", "rent-ready", "legal", "safety"],
        "Self Care": ["phys-health", "sub-use", "support-sys"],
        "Sustainable Work": [
            "career-res", "education", "emp-stablility", "future-hopes", "income-met"
        ],
        "Safety & Stability + Self-Care + Sustainable Work": [
            "food", "rent-ready", "legal", "safety", "phys-health", "sub-use",
            "support-sys", "career-res", "education", "emp-stablility",
            "future-hopes", "income-met"
        ]
    }
}

# Program year definitions
PROGRAM_YEARS = {
    '2024': {
        'start': datetime(2022, 1, 1),
        'end': datetime(2024, 9, 30, 23, 59, 59),
        'prev': None
    },
    '2025': {
        'start': datetime(2024, 10, 1),
        'end': datetime(2025, 9, 30, 23, 59, 59),
        'prev': '2024'
    },
    '2026': {
        'start': datetime(2025, 10, 1),
        'end': datetime(2026, 9, 30, 23, 59, 59),
        'prev': '2025'
    }
}


def get_sheets_client():
    """Get authenticated Google Sheets client"""
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]

    creds_dict = json.loads(os.environ['GOOGLE_SHEETS_CREDS'])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)


def read_sheet_data(client, sheet_id, worksheet_name):
    """Read all data from a worksheet"""
    print(f"Reading data from {worksheet_name}...")
    spreadsheet = client.open_by_key(sheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name)
    data = worksheet.get_all_values()
    print(f"  Loaded {len(data)-1} rows")
    return data


def write_sheet_data(client, sheet_id, worksheet_name, data):
    """Write data to a worksheet, clearing it first"""
    print(f"Writing {len(data)-1} rows to {worksheet_name}...")
    spreadsheet = client.open_by_key(sheet_id)

    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
        worksheet.clear()
    except:
        # Create worksheet if it doesn't exist
        worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=len(data), cols=len(data[0]))

    worksheet.update('A1', data)
    print(f"  ✓ Written successfully")


def get_column_indices(headers):
    """Convert list of headers to column index dict"""
    return {col: headers.index(col) if col in headers else -1 for col in headers}


def get_survey_code_name_mapping(assess_dict):
    """Create mapping from survey name to survey code"""
    headers = assess_dict[0]
    col = get_column_indices(headers)

    mapping = {}
    for row in assess_dict[1:]:
        survey_code = row[col['TreatmentCode']]
        survey_name = row[col['Document']]
        if survey_name and survey_code:
            mapping[survey_name] = survey_code

    print(f"Created mapping for {len(mapping)} Survey Names")
    return mapping


def get_value_cleaning_mapping(assess_dict):
    """Create mapping from raw values to cleaned values"""
    headers = assess_dict[0]
    col = get_column_indices(headers)

    mapping = {}
    for row in assess_dict[1:]:
        raw_value = row[col['RawValue']]
        cleaned_value = row[col['CleanedValue']]

        # Allow 0 as valid value - only skip truly empty
        if raw_value != '' and cleaned_value != '':
            # Convert to number if possible
            try:
                mapping[raw_value] = float(cleaned_value) if '.' in str(cleaned_value) else int(cleaned_value)
            except:
                mapping[raw_value] = cleaned_value

    print(f"Created value cleaning mapping for {len(mapping)} values")
    return mapping


def get_unique_treatment_question_pairs(assess_dict):
    """Get unique combinations of survey code and question code"""
    headers = assess_dict[0]
    col = get_column_indices(headers)

    unique_pairs = set()
    result = []

    for row in assess_dict[1:]:
        survey_code = row[col['TreatmentCode']]
        survey_name = row[col['Document']]
        question_code = row[col['QuestionCode']]
        key = f"{survey_code}|{question_code}"

        if key not in unique_pairs:
            unique_pairs.add(key)
            result.append((survey_code, survey_name, question_code))

    print(f"Found {len(result)} unique survey-question pairs")
    return result


def get_patient_name_mapping(treatment_thread):
    """Create mapping from patient ID to names"""
    headers = treatment_thread[0]
    col = get_column_indices(headers)

    name_map = {}
    for row in treatment_thread[1:]:
        patient_id = row[col['ClientID']]
        if patient_id and patient_id not in name_map:
            name_map[patient_id] = {
                'FirstName': row[col['FirstName']] or '',
                'LastName': row[col['LastName']] or ''
            }

    print(f"Created name mapping for {len(name_map)} patients")
    return name_map


def create_skeleton(daily_summary, unique_pairs):
    """Create skeleton of all expected patient/survey/question combinations"""
    print("Creating skeleton...")
    headers = daily_summary[0]
    col = get_column_indices(headers)

    skeleton_data = [['PatientID', 'TreatmentDate', 'TreatmentCode', 'SurveyName', 'QuestionCode']]

    for row in daily_summary[1:]:
        patient_id = row[col['PatientID']]
        survey_code = row[col['TreatmentCode']]
        survey_date = row[col['TreatmentDT']]

        # Convert to number if string
        try:
            survey_code = int(survey_code) if survey_code else None
        except:
            continue

        # Filter to specific survey codes
        if survey_code not in [9000, 1000, 1001]:
            continue

        # Add row for each question in this survey
        for pair_survey_code, survey_name, question_code in unique_pairs:
            if pair_survey_code == str(survey_code):
                skeleton_data.append([patient_id, survey_date, survey_code, survey_name, question_code])

    print(f"  Created skeleton with {len(skeleton_data)-1} rows")
    return skeleton_data


def generate_instance_codes(skeleton_data):
    """Add treatment instance codes and question treatment instance codes"""
    print("Generating instance codes...")
    headers = skeleton_data[0]

    output_data = [headers + ['TreatmentInstanceCode', 'QuestionTreatmentInstanceCode']]

    for row in skeleton_data[1:]:
        patient_id = row[0]
        survey_date = row[1]
        question_code = row[4]

        # Parse date and format as M-D-YYYY-HH-mm
        try:
            date_obj = parse_date_flexible(survey_date)
            formatted_date = date_obj.strftime(DATE_FORMAT)
        except:
            formatted_date = str(survey_date)

        treatment_instance_code = f"{patient_id}-{formatted_date}"
        question_treatment_instance_code = f"{treatment_instance_code}-{question_code}"

        output_data.append(row + [treatment_instance_code, question_treatment_instance_code])

    print(f"  Generated codes for {len(output_data)-1} rows")
    return output_data


def process_treatment_thread_export(treatment_thread, survey_mapping, value_cleaning_map):
    """Process treatment thread export with cleaning and codes"""
    print("Processing treatment thread export...")
    headers = treatment_thread[0]
    col = get_column_indices(headers)

    full_headers = headers + ['TreatmentCode', 'TreatmentInstanceCode',
                              'QuestionTreatmentInstanceCode', 'CleanedValue']
    full_data = []

    value_col_index = headers.index('Value')

    for row in treatment_thread[1:]:
        patient_id = row[col['ClientID']]
        date_value = row[col['Date']]
        time_value = row[col['Time']]
        survey_name = row[col['Document']]
        question_code = row[col['Code']]
        raw_value = row[value_col_index]

        survey_code = survey_mapping.get(survey_name, '')

        # Clean the value
        cleaned_value = value_cleaning_map.get(raw_value, raw_value)

        # Parse datetime
        try:
            date_obj = parse_date_flexible(date_value)
            time_obj = parse_date_flexible(time_value)

            # Combine date and time
            combined = datetime(date_obj.year, date_obj.month, date_obj.day,
                              time_obj.hour, time_obj.minute)
            formatted_date = combined.strftime(DATE_FORMAT)
        except:
            formatted_date = str(date_value)

        treatment_instance_code = f"{patient_id}-{formatted_date}"
        question_treatment_instance_code = f"{treatment_instance_code}-{question_code}"

        full_data.append(row + [survey_code, treatment_instance_code,
                               question_treatment_instance_code, cleaned_value])

    print(f"  Processed {len(full_data)} rows")
    return [full_headers] + full_data


def join_skeleton_with_responses(skeleton_data, response_data):
    """Join skeleton with actual responses"""
    print("Joining skeleton with responses...")
    skeleton_headers = skeleton_data[0]
    response_headers = response_data[0]

    # Build lookup map
    response_map = {}
    response_key_index = response_headers.index('QuestionTreatmentInstanceCode')
    response_value_index = response_headers.index('CleanedValue')

    for row in response_data[1:]:
        key = row[response_key_index]
        value = row[response_value_index]
        response_map[key] = value

    print(f"  Built response map with {len(response_map)} responses")

    # Join data
    output_data = [skeleton_headers + ['Value']]
    skeleton_key_index = skeleton_headers.index('QuestionTreatmentInstanceCode')

    for row in skeleton_data[1:]:
        key = row[skeleton_key_index]
        value = response_map.get(key, '')
        output_data.append(row + [value])

    print(f"  Joined data: {len(output_data)-1} rows")
    return output_data


def parse_date_flexible(date_value):
    """Parse date from various formats"""
    if isinstance(date_value, datetime):
        return date_value

    if not isinstance(date_value, str):
        return datetime.now()

    # Try multiple date formats
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%m/%d/%Y %I:%M:%S %p',  # 4/11/2022 11:53:28 PM
        '%m/%d/%Y %H:%M:%S',
        '%Y-%m-%d',
        '%m/%d/%Y'
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_value, fmt)
        except:
            continue

    # If all fail, return current time
    print(f"Warning: Could not parse date '{date_value}'")
    return datetime.now()


def fill_forward_values(joined_data):
    """Fill forward missing values per patient+question combination"""
    print("Filling forward values...")
    headers = joined_data[0]
    col = get_column_indices(headers)

    output_headers = headers + ['IsImputed']

    # Sort by PatientID, QuestionCode, TreatmentDate
    data_rows = joined_data[1:]
    data_rows.sort(key=lambda x: (
        x[col['PatientID']],
        x[col['QuestionCode']],
        parse_date_flexible(x[col['TreatmentDate']])
    ))

    # Fill forward
    last_values = {}
    output_data = [output_headers]

    for row in data_rows:
        patient_id = row[col['PatientID']]
        question_code = row[col['QuestionCode']]
        value = row[col['Value']]
        key = f"{patient_id}|{question_code}"

        if value == '' or value is None:
            if key in last_values:
                row[col['Value']] = last_values[key]
                is_imputed = 'Yes'
            else:
                is_imputed = ''
        else:
            last_values[key] = value
            is_imputed = 'No'

        output_data.append(row + [is_imputed])

    print(f"  Fill forward complete: {len(output_data)-1} rows")
    return output_data


def stage_data(data, name_map, column_order):
    """Add patient names and reorder columns"""
    print("Staging data...")
    headers = data[0]
    col = get_column_indices(headers)

    enriched_headers = headers + ['FirstName', 'LastName']
    enriched_data = [enriched_headers]

    for row in data[1:]:
        patient_id = row[col['PatientID']]
        names = name_map.get(patient_id, {'FirstName': '', 'LastName': ''})
        enriched_data.append(row + [names['FirstName'], names['LastName']])

    # Reorder if specified
    if column_order:
        column_indices = [enriched_headers.index(col) for col in column_order]
        output_data = [column_order]

        for row in enriched_data[1:]:
            reordered_row = [row[i] for i in column_indices]
            output_data.append(reordered_row)

        print(f"  Staged {len(output_data)-1} rows with {len(column_order)} columns")
        return output_data

    print(f"  Staged {len(enriched_data)-1} rows")
    return enriched_data


def build_client_date_frame_distinct(assessment_frame_values):
    """
    Build client date frame with distinct start/end assessments per program year.
    Determines eligibility for metrics based on having distinct start/end assessments.
    """
    print("Building client date frame...")

    if not assessment_frame_values or len(assessment_frame_values) < 2:
        return [['No data']]

    headers = assessment_frame_values[0]
    col = get_column_indices(headers)

    # Group by PatientID|TreatmentCode
    groups = {}

    for row in assessment_frame_values[1:]:
        patient_id = row[col['PatientID']]
        treatment_code = row[col['TreatmentCode']]
        instance_code = row[col['TreatmentInstanceCode']]
        treatment_date = row[col['TreatmentDate']]

        if not patient_id or not treatment_code or not instance_code:
            continue

        # Parse date
        try:
            date_obj = parse_date_flexible(treatment_date)
        except:
            continue

        key = f"{patient_id}|{treatment_code}"

        if key not in groups:
            groups[key] = {
                'patientID': patient_id,
                'firstName': row[col['FirstName']] or '',
                'lastName': row[col['LastName']] or '',
                'treatmentCode': treatment_code,
                'surveyName': row[col['SurveyName']] or '',
                'instances': {}
            }

        # Store date for each instance (dedupe)
        if instance_code not in groups[key]['instances']:
            groups[key]['instances'][instance_code] = date_obj
        else:
            # Keep earliest if duplicates
            if date_obj < groups[key]['instances'][instance_code]:
                groups[key]['instances'][instance_code] = date_obj

    # Output headers
    out_headers = [
        'PatientID', 'FirstName', 'LastName', 'TreatmentCode', 'SurveyName',

        '2024_start_date', '2024_start_treatment_instance_code',
        '2024_end_date', '2024_end_treatment_instance_code',
        'Include_in_2024_Metrics_Denominator',

        '2025_start_date', '2025_start_treatment_instance_code',
        '2025_end_date', '2025_end_treatment_instance_code',
        'Include_in_2025_Metrics_Denominator',

        '2026_start_date', '2026_start_treatment_instance_code',
        '2026_end_date', '2026_end_treatment_instance_code',
        'Include_in_2026_Metrics_Denominator',

        'overall_start_date', 'overall_start_treatment_instance_code',
        'overall_end_date', 'overall_end_treatment_instance_code',
        'Include_in_All_Time_Metrics_Denominator'
    ]

    out = [out_headers]

    for key, group in groups.items():
        instances_arr = [{'code': code, 'date': date}
                        for code, date in group['instances'].items()]
        instances_arr.sort(key=lambda x: x['date'])

        total_assessments = len(instances_arr)

        # Overall distinct start/end
        overall_end = instances_arr[-1] if total_assessments else None
        overall_start = None

        if overall_end:
            for inst in instances_arr:
                if inst['code'] != overall_end['code']:
                    overall_start = inst
                    break

        include_all_time = 'Yes' if (total_assessments >= 2 and overall_start and
                                     overall_end and overall_start['code'] != overall_end['code']) else ''

        # Bucket by program year
        by_py = {}
        for year, config in PROGRAM_YEARS.items():
            by_py[year] = [inst for inst in instances_arr
                          if config['start'] <= inst['date'] <= config['end']]
            by_py[year].sort(key=lambda x: x['date'])

        def compute_year(year):
            cur = by_py[year]
            ending = cur[-1] if cur else None

            if not ending:
                return {
                    'startDate': '', 'startCode': '',
                    'endDate': '', 'endCode': '', 'include': ''
                }

            # Find starting assessment
            starting = None
            for inst in cur:
                if inst['code'] != ending['code']:
                    starting = inst
                    break

            # If no starting in current PY, use latest from previous PY
            if not starting:
                prev_year = PROGRAM_YEARS[year].get('prev')
                if prev_year and by_py[prev_year]:
                    prev_latest = by_py[prev_year][-1]
                    if prev_latest['code'] != ending['code']:
                        starting = prev_latest

            eligible = (total_assessments >= 2 and starting and
                       starting['code'] != ending['code'])

            return {
                'startDate': starting['date'] if starting else '',
                'startCode': starting['code'] if starting else '',
                'endDate': ending['date'],
                'endCode': ending['code'],
                'include': 'Yes' if eligible else ''
            }

        y2024 = compute_year('2024')
        y2025 = compute_year('2025')
        y2026 = compute_year('2026')

        out.append([
            group['patientID'], group['firstName'], group['lastName'],
            group['treatmentCode'], group['surveyName'],

            y2024['startDate'], y2024['startCode'],
            y2024['endDate'], y2024['endCode'],
            y2024['include'],

            y2025['startDate'], y2025['startCode'],
            y2025['endDate'], y2025['endCode'],
            y2025['include'],

            y2026['startDate'], y2026['startCode'],
            y2026['endDate'], y2026['endCode'],
            y2026['include'],

            overall_start['date'] if overall_start else '',
            overall_start['code'] if overall_start else '',
            overall_end['date'] if overall_end else '',
            overall_end['code'] if overall_end else '',
            include_all_time
        ])

    print(f"  Built client date frame: {len(out)-1} rows")
    return out


def pivot_client_date_frame_to_long_with_aggregations(
    client_date_frame_values, assessment_frame_values, aggregation_config
):
    """
    Pivot client date frame to long format with per-question rows plus aggregations.
    Includes program year rollups and custom category rollups.
    """
    print("Pivoting to long format with aggregations...")

    if not client_date_frame_values or len(client_date_frame_values) < 2:
        return [['No client_date_frame data']]
    if not assessment_frame_values or len(assessment_frame_values) < 2:
        raise Exception('Requires assessment_frame_values')

    aggregation_config = aggregation_config or {}

    # Parse headers
    c_hdr = client_date_frame_values[0]
    c_col = get_column_indices(c_hdr)

    a_hdr = assessment_frame_values[0]
    a_col = get_column_indices(a_hdr)

    # Build lookup: (TreatmentInstanceCode|QuestionCode) -> Value
    value_by_instance_question = {}
    questions_by_treatment = {}

    for row in assessment_frame_values[1:]:
        inst = row[a_col['TreatmentInstanceCode']]
        t_code = row[a_col['TreatmentCode']]
        q_code = row[a_col['QuestionCode']]
        val = row[a_col['Value']]

        if not inst or not t_code or not q_code:
            continue

        key = f"{inst}|{q_code}"
        if key not in value_by_instance_question:
            value_by_instance_question[key] = val

        if t_code not in questions_by_treatment:
            questions_by_treatment[t_code] = set()
        questions_by_treatment[t_code].add(q_code)

    def get_value(inst_code, q_code):
        if not inst_code:
            return ''
        v = value_by_instance_question.get(f"{inst_code}|{q_code}")
        return '' if v is None else v

    def to_number_or_none(v):
        if v == '' or v is None:
            return None
        try:
            return float(v)
        except:
            return None

    def sum_numeric(values):
        total = 0
        saw_any = False
        for v in values:
            n = to_number_or_none(v)
            if n is not None:
                total += n
                saw_any = True
        return total if saw_any else ''

    def movement(start_val, end_val):
        s = to_number_or_none(start_val)
        e = to_number_or_none(end_val)
        if s is None or e is None:
            return ''
        return e - s

    def to_bool(v):
        if v in [True, 1]:
            return True
        if v in [False, 0]:
            return False
        if isinstance(v, str):
            return v.strip().lower() in ['yes', 'true', 'y']
        return False

    # Output headers
    out_headers = [
        'PatientID', 'FirstName', 'LastName', 'SurveyName', 'TreatmentCode',
        'QuestionCode', 'ProgramYear', 'StartValue', 'EndValue', 'Movement',
        'StartAssessmentDate', 'EndAssessmentDate',
        'StartTreatmentInstanceCode', 'EndTreatmentInstanceCode',
        'IsEligibleDenominator'
    ]
    out = [out_headers]

    program_years = [
        {
            'label': '2024',
            'start_code_col': '2024_start_treatment_instance_code',
            'end_code_col': '2024_end_treatment_instance_code',
            'start_date_col': '2024_start_date',
            'end_date_col': '2024_end_date',
            'eligible_col': 'Include_in_2024_Metrics_Denominator'
        },
        {
            'label': '2025',
            'start_code_col': '2025_start_treatment_instance_code',
            'end_code_col': '2025_end_treatment_instance_code',
            'start_date_col': '2025_start_date',
            'end_date_col': '2025_end_date',
            'eligible_col': 'Include_in_2025_Metrics_Denominator'
        },
        {
            'label': '2026',
            'start_code_col': '2026_start_treatment_instance_code',
            'end_code_col': '2026_end_treatment_instance_code',
            'start_date_col': '2026_start_date',
            'end_date_col': '2026_end_date',
            'eligible_col': 'Include_in_2026_Metrics_Denominator'
        },
        {
            'label': 'OVERALL',
            'start_code_col': 'overall_start_treatment_instance_code',
            'end_code_col': 'overall_end_treatment_instance_code',
            'start_date_col': 'overall_start_date',
            'end_date_col': 'overall_end_date',
            'eligible_col': 'Include_in_All_Time_Metrics_Denominator'
        }
    ]

    def push_row(base, q_code, py_label, start_val, end_val, start_date,
                end_date, start_inst, end_inst, eligible_bool):
        out.append([
            base['patientID'], base['firstName'], base['lastName'],
            base['surveyName'], base['treatmentCode'],
            q_code, py_label, start_val, end_val, movement(start_val, end_val),
            start_date or '', end_date or '',
            start_inst or '', end_inst or '',
            eligible_bool
        ])

    # Expand to long format with rollups
    for row in client_date_frame_values[1:]:
        base = {
            'patientID': row[c_col['PatientID']],
            'firstName': row[c_col['FirstName']] or '',
            'lastName': row[c_col['LastName']] or '',
            'surveyName': row[c_col['SurveyName']] or '',
            'treatmentCode': row[c_col['TreatmentCode']]
        }

        if not base['patientID'] or not base['treatmentCode']:
            continue

        treatment_questions = sorted(questions_by_treatment.get(base['treatmentCode'], set()))
        custom_cats = aggregation_config.get(str(base['treatmentCode']), {})

        for py in program_years:
            start_inst = row[c_col[py['start_code_col']]] or ''
            end_inst = row[c_col[py['end_code_col']]] or ''
            start_date = row[c_col[py['start_date_col']]] or ''
            end_date = row[c_col[py['end_date_col']]] or ''
            eligible_bool = to_bool(row[c_col[py['eligible_col']]])

            # 1) Per-question rows
            for q_code in treatment_questions:
                s_val = get_value(start_inst, q_code)
                e_val = get_value(end_inst, q_code)
                push_row(base, q_code, py['label'], s_val, e_val,
                        start_date, end_date, start_inst, end_inst, eligible_bool)

            # 2) TOTAL rollup
            total_start = sum_numeric([get_value(start_inst, q) for q in treatment_questions])
            total_end = sum_numeric([get_value(end_inst, q) for q in treatment_questions])
            push_row(base, '__TOTAL__', py['label'], total_start, total_end,
                    start_date, end_date, start_inst, end_inst, eligible_bool)

            # 3) Custom category rollups
            for cat_name, q_list in custom_cats.items():
                cat_start = sum_numeric([get_value(start_inst, q) for q in q_list])
                cat_end = sum_numeric([get_value(end_inst, q) for q in q_list])
                push_row(base, f"__CAT__:{cat_name}", py['label'], cat_start, cat_end,
                        start_date, end_date, start_inst, end_inst, eligible_bool)

    print(f"  Pivoted to long format: {len(out)-1} rows")
    return out


def pivot_assessment_data(survey_code, question_codes, data_frame):
    """Pivot assessment data to wide format"""
    print(f"Pivoting assessment data for survey {survey_code}...")

    headers = data_frame[0]
    col = get_column_indices(headers)

    # Group by PatientID + TreatmentDate
    grouped_data = {}

    for row in data_frame[1:]:
        if str(row[col['TreatmentCode']]) != str(survey_code):
            continue

        patient_id = row[col['PatientID']]
        first_name = row[col['FirstName']]
        last_name = row[col['LastName']]
        treatment_date = row[col['TreatmentDate']]
        q_code = row[col['QuestionCode']]
        value = row[col['Value']]

        key = f"{patient_id}|{treatment_date}"

        if key not in grouped_data:
            grouped_data[key] = {
                'patientID': patient_id,
                'firstName': first_name,
                'lastName': last_name,
                'treatmentDate': treatment_date,
                'questions': {}
            }

        grouped_data[key]['questions'][q_code] = value

    # Build output
    output_headers = ['PatientID', 'FirstName', 'LastName', 'TreatmentDate'] + question_codes
    output_data = [output_headers]

    # Sort by PatientID and TreatmentDate
    sorted_keys = sorted(grouped_data.keys(), key=lambda k: (
        grouped_data[k]['patientID'],
        grouped_data[k]['treatmentDate']
    ))

    for key in sorted_keys:
        record = grouped_data[key]
        row = [
            record['patientID'],
            record['firstName'],
            record['lastName'],
            record['treatmentDate']
        ]

        for q in question_codes:
            row.append(record['questions'].get(q, ''))

        output_data.append(row)

    print(f"  Pivoted {len(output_data)-1} rows")
    return output_data


def main():
    """Main data cleaning pipeline"""
    print("="*60)
    print("Starting data cleaning pipeline...")
    print("="*60)

    # Get Google Sheets client
    client = get_sheets_client()

    # Read input data
    daily_summary = read_sheet_data(client, SHEET_ID, 'client_summary_export')
    treatment_thread = read_sheet_data(client, SHEET_ID, 'treatment_thread_export')
    assess_dict = read_sheet_data(client, SHEET_ID, 'assesment_dictionary')

    # Build mappings
    survey_mapping = get_survey_code_name_mapping(assess_dict)
    value_cleaning_map = get_value_cleaning_mapping(assess_dict)
    name_map = get_patient_name_mapping(treatment_thread)
    unique_pairs = get_unique_treatment_question_pairs(assess_dict)

    # Create skeleton
    skeleton = create_skeleton(daily_summary, unique_pairs)
    with_codes = generate_instance_codes(skeleton)

    # Process treatment thread
    processed_tt = process_treatment_thread_export(
        treatment_thread, survey_mapping, value_cleaning_map
    )

    # Join and fill forward
    joined_data = join_skeleton_with_responses(with_codes, processed_tt)
    filled_data = fill_forward_values(joined_data)

    # Stage final assessment frame
    column_order = [
        'QuestionTreatmentInstanceCode', 'TreatmentInstanceCode', 'PatientID',
        'FirstName', 'LastName', 'TreatmentCode', 'SurveyName', 'TreatmentDate',
        'QuestionCode', 'Value', 'IsImputed'
    ]
    final_data = stage_data(filled_data, name_map, column_order)

    # Build client date frame
    client_date_frame = build_client_date_frame_distinct(final_data)

    # Generate output frames
    wide_data = pivot_assessment_data(SS_SURVEY_CODE, SS_QUESTION_CODES, final_data)
    long_with_aggs = pivot_client_date_frame_to_long_with_aggregations(
        client_date_frame, final_data, AGGREGATION_CONFIG
    )

    # Write output sheets
    print("\n" + "="*60)
    print("Writing output sheets...")
    print("="*60)
    write_sheet_data(client, SHEET_ID, 'long_frame', final_data)
    write_sheet_data(client, SHEET_ID, 'wide_frame', wide_data)
    write_sheet_data(client, SHEET_ID, 'yoy_frame', long_with_aggs)

    print("\n" + "="*60)
    print("✓ Data cleaning pipeline completed successfully!")
    print("="*60)


if __name__ == '__main__':
    main()
