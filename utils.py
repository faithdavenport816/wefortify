"""Shared utilities for ReliaTrax scrapers"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
from datetime import datetime


def setup_driver():
    """Set up headless Chrome driver for GitHub Actions"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    chrome_options.add_argument('--enable-javascript')

    prefs = {
        "download.default_directory": "/tmp",
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)

    return driver


def login_to_reliatrax(driver, username, password):
    """Log into ReliaTrax"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    import time

    print("Navigating to login page...")
    driver.get("https://wefortify.reliatrax.net/Account.aspx/Login")

    try:
        wait = WebDriverWait(driver, 20)

        print("Waiting for page to load...")
        time.sleep(2)

        print(f"Page title: {driver.title}")
        print(f"Current URL: {driver.current_url}")

        print("Looking for username field...")
        username_field = wait.until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_field.clear()
        username_field.send_keys(username)
        print("Username entered successfully")

        print("Looking for password field...")
        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        password_field.send_keys(password)
        print("Password entered successfully")

        print("Looking for login button...")
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        print("Login button clicked")

        time.sleep(3)
        print("Login successful!")

    except TimeoutException as e:
        print(f"Login failed with timeout: {e}")
        print("Saving screenshot for debugging...")
        driver.save_screenshot("/tmp/login_error.png")
        print("Saving page source for debugging...")
        with open("/tmp/page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        raise


def get_sheets_client():
    """Setup and return Google Sheets client"""
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']

    creds_dict = json.loads(os.environ['GOOGLE_SHEETS_CREDS'])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    return client


def write_to_sheets(data, sheet_id, worksheet_name=None, clear_first=True):
    """Write extracted data to Google Sheets

    Args:
        data: Dict with 'headers' and 'rows' keys
        sheet_id: Google Sheets ID
        worksheet_name: Name of the worksheet/tab (e.g., "Sheet1", "Treatment Data").
                       If None, uses the first sheet.
        clear_first: If True, clears existing data before writing
    """
    print("Connecting to Google Sheets...")

    client = get_sheets_client()
    spreadsheet = client.open_by_key(sheet_id)

    # Select the worksheet by name, or use first sheet if not specified
    if worksheet_name:
        print(f"Opening worksheet: {worksheet_name}")
        try:
            sheet = spreadsheet.worksheet(worksheet_name)
        except Exception as e:
            print(f"Worksheet '{worksheet_name}' not found. Available worksheets:")
            for ws in spreadsheet.worksheets():
                print(f"  - {ws.title}")
            raise Exception(f"Worksheet '{worksheet_name}' does not exist") from e
    else:
        sheet = spreadsheet.sheet1

    if clear_first:
        print("Clearing existing sheet data...")
        sheet.clear()

    # Add timestamp column to headers
    headers = data["headers"].copy()
    if "Export Timestamp" not in headers:
        headers.append("Export Timestamp")

    # Prepare all rows with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows_with_timestamp = []

    for row in data["rows"]:
        row_with_timestamp = row + [timestamp]
        rows_with_timestamp.append(row_with_timestamp)

    # Add headers and all data in one batch
    print(f"Writing headers and {len(rows_with_timestamp)} rows...")
    all_data = [headers] + rows_with_timestamp
    sheet.update('A1', all_data)

    print(f"Successfully wrote {len(data['rows'])} rows to worksheet '{sheet.title}'!")


def wait_for_csv_download(download_dir="/tmp", max_wait=30):
    """Wait for CSV file to download and return the file path

    Args:
        download_dir: Directory where downloads are saved
        max_wait: Maximum time to wait in seconds

    Returns:
        Path to downloaded CSV file
    """
    import time

    print("Waiting for CSV file to download...")
    downloaded_file = None

    for _ in range(max_wait):
        time.sleep(1)
        csv_files = [f for f in os.listdir(download_dir) if f.endswith('.csv')]
        if csv_files:
            csv_files_with_path = [os.path.join(download_dir, f) for f in csv_files]
            downloaded_file = max(csv_files_with_path, key=os.path.getmtime)
            print(f"Found downloaded CSV file: {os.path.basename(downloaded_file)}")
            return downloaded_file

    raise Exception("CSV download timed out")


def read_csv_file(file_path):
    """Read CSV file and return data in the expected format"""
    import csv

    print(f"Reading CSV file: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            all_rows = list(csv_reader)

        if not all_rows:
            print("CSV file is empty")
            return {"headers": [], "rows": []}

        headers = all_rows[0]
        rows_data = all_rows[1:]

        print(f"CSV loaded: {len(rows_data)} rows with {len(headers)} columns")

        if rows_data:
            print(f"Headers: {headers[:5] if len(headers) > 5 else headers}")
            print(f"First row sample: {rows_data[0][:5] if len(rows_data[0]) > 5 else rows_data[0]}")

        return {"headers": headers, "rows": rows_data}

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return {"headers": [], "rows": []}


def clear_old_csv_files(download_dir="/tmp"):
    """Clear any existing CSV files in download directory"""
    for file in os.listdir(download_dir):
        if file.endswith('.csv'):
            os.remove(os.path.join(download_dir, file))
            print(f"Removed old CSV file: {file}")
