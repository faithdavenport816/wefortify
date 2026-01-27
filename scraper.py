from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import time
import csv
from datetime import datetime

def setup_driver():
    """Set up headless Chrome driver for GitHub Actions"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')  # Use new headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # Enable JavaScript
    chrome_options.add_argument('--enable-javascript')

    # Set download directory
    prefs = {
        "download.default_directory": "/tmp",
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=chrome_options)

    # Set page load timeout
    driver.set_page_load_timeout(30)

    return driver

def login_to_reliatrax(driver, username, password):
    """Log into ReliaTrax"""
    print("Navigating to login page...")
    driver.get("https://wefortify.reliatrax.net/Account.aspx/Login")

    try:
        # Wait for login form to load
        wait = WebDriverWait(driver, 20)

        # Wait for page to be fully loaded
        print("Waiting for page to load...")
        time.sleep(2)

        print(f"Page title: {driver.title}")
        print(f"Current URL: {driver.current_url}")

        # Find and fill username field
        print("Looking for username field...")
        username_field = wait.until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_field.clear()
        username_field.send_keys(username)
        print("Username entered successfully")

        # Find and fill password field
        print("Looking for password field...")
        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        password_field.send_keys(password)
        print("Password entered successfully")

        # Click login button
        print("Looking for login button...")
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        print("Login button clicked")

        # Wait for redirect after login
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

def export_treatment_data(driver):
    """Navigate to export page and trigger CSV download"""
    print("Navigating to Treatment Thread Export page...")
    driver.get("https://wefortify.reliatrax.net/TreatmentThread.aspx/ThreadExport")

    try:
        wait = WebDriverWait(driver, 20)

        # Wait for page to load
        print("Waiting for export page to load...")
        time.sleep(2)

        # Find the CSV Row View button
        print("Looking for CSV Row View button...")
        csv_button = wait.until(EC.presence_of_element_located((By.ID, "btCsvRowDownload")))
        print("Found CSV Row View button!")

        # Find and check the "Include All Values" checkbox
        print("Looking for 'Include All Values' checkbox...")
        include_all_checkbox = driver.find_element(By.ID, "includeAllValues")

        if not include_all_checkbox.is_selected():
            print("Checking 'Include All Values' checkbox...")
            include_all_checkbox.click()
            time.sleep(1)
        else:
            print("Checkbox already checked")

        # Clear any existing CSV files in download directory
        download_dir = "/tmp"
        for file in os.listdir(download_dir):
            if file.endswith('.csv'):
                os.remove(os.path.join(download_dir, file))
                print(f"Removed old CSV file: {file}")

        print("Clicking CSV export button to download file...")
        csv_button.click()

        # Wait for file to download
        print("Waiting for CSV file to download...")
        max_wait = 30  # Maximum wait time in seconds
        downloaded_file = None

        for i in range(max_wait):
            time.sleep(1)
            # Look for CSV files in download directory
            csv_files = [f for f in os.listdir(download_dir) if f.endswith('.csv')]
            if csv_files:
                # Get the most recent CSV file
                csv_files_with_path = [os.path.join(download_dir, f) for f in csv_files]
                downloaded_file = max(csv_files_with_path, key=os.path.getmtime)
                print(f"Found downloaded CSV file: {os.path.basename(downloaded_file)}")
                break

        if not downloaded_file:
            print("CSV file was not downloaded within timeout period")
            driver.save_screenshot("/tmp/export_timeout.png")
            raise Exception("CSV download timed out")

        # Read the CSV file
        csv_data = read_csv_file(downloaded_file)
        return csv_data

    except Exception as e:
        print(f"Error during export: {e}")
        driver.save_screenshot("/tmp/export_error.png")
        print("Saving page source for debugging...")
        with open("/tmp/export_error_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        raise

def read_csv_file(file_path):
    """Read CSV file and return data in the expected format"""
    print(f"Reading CSV file: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            all_rows = list(csv_reader)

        if not all_rows:
            print("CSV file is empty")
            return {"headers": [], "rows": []}

        # First row is headers
        headers = all_rows[0]
        # Rest are data rows
        rows_data = all_rows[1:]

        print(f"CSV loaded: {len(rows_data)} rows with {len(headers)} columns")

        # Save a sample for debugging
        if rows_data:
            print(f"Headers: {headers[:5] if len(headers) > 5 else headers}")
            print(f"First row sample: {rows_data[0][:5] if len(rows_data[0]) > 5 else rows_data[0]}")

        return {"headers": headers, "rows": rows_data}

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return {"headers": [], "rows": []}

def write_to_sheets(data):
    """Write extracted data to Google Sheets"""
    print("Connecting to Google Sheets...")
    
    # Setup Google Sheets API
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    creds_dict = json.loads(os.environ['GOOGLE_SHEETS_CREDS'])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # Open your sheet
    sheet_id = os.environ['SHEET_ID']
    sheet = client.open_by_key(sheet_id).sheet1
    
    # Check if sheet is empty (first run)
    existing_data = sheet.get_all_values()
    
    if not existing_data:
        # First run - add headers
        print("First run detected. Adding headers...")
        if data["headers"]:
            sheet.append_row(data["headers"])
    
    # Add timestamp column if not present
    headers = data["headers"]
    if "Export Timestamp" not in headers:
        headers.append("Export Timestamp")
    
    # Append all rows with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for row in data["rows"]:
        row_with_timestamp = row + [timestamp]
        sheet.append_row(row_with_timestamp)
    
    print(f"Successfully wrote {len(data['rows'])} rows to Google Sheet!")

def main():
    driver = None
    
    try:
        # Get credentials from environment
        username = os.environ['RELIATRAX_USERNAME']
        password = os.environ['RELIATRAX_PASSWORD']
        
        # Setup driver
        driver = setup_driver()
        
        # Login
        login_to_reliatrax(driver, username, password)
        
        # Export data
        data = export_treatment_data(driver)
        
        if data["rows"]:
            # Write to Google Sheets
            write_to_sheets(data)
            print("Export completed successfully!")
        else:
            print("No data to export.")
        
    except Exception as e:
        print(f"Error in main execution: {e}")
        raise
        
    finally:
        if driver:
            driver.quit()
            print("Browser closed.")

if __name__ == '__main__':
    main()