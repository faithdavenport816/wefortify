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
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Set download directory
    prefs = {
        "download.default_directory": "/tmp",
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def login_to_reliatrax(driver, username, password):
    """Log into ReliaTrax"""
    print("Navigating to login page...")
    driver.get("https://wefortify.reliatrax.net/Account.aspx/Login")
    
    try:
        # Wait for login form to load
        wait = WebDriverWait(driver, 15)
        
        # Find and fill username field (adjust selectors based on actual page)
        username_field = wait.until(
            EC.presence_of_element_located((By.ID, "txtUsername"))
        )
        username_field.clear()
        username_field.send_keys(username)
        
        # Find and fill password field
        password_field = driver.find_element(By.ID, "txtPassword")
        password_field.clear()
        password_field.send_keys(password)
        
        # Click login button
        login_button = driver.find_element(By.ID, "btnLogin")
        login_button.click()
        
        # Wait for redirect after login
        time.sleep(3)
        print("Login successful!")
        
    except TimeoutException:
        print("Login page elements not found. Saving screenshot for debugging...")
        driver.save_screenshot("/tmp/login_error.png")
        raise

def export_treatment_data(driver):
    """Navigate to export page and trigger export"""
    print("Navigating to Treatment Thread Export page...")
    driver.get("https://wefortify.reliatrax.net/TreatmentThread.aspx/ThreadExport")
    
    try:
        wait = WebDriverWait(driver, 15)
        
        # Wait for page to load
        wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'CSV Row View')]")))
        
        # Set date range to "All Folders" and include all values
        # Check the "Include All Values" checkbox if not already checked
        include_all_checkbox = driver.find_element(By.ID, "chkIncludeAllValues")
        if not include_all_checkbox.is_selected():
            include_all_checkbox.click()
        
        print("Clicking CSV Row View export...")
        
        # Click the CSV Row View button
        csv_button = driver.find_element(By.XPATH, "//button[contains(text(), 'CSV Row View')]")
        csv_button.click()
        
        # Wait for the data table to appear (it visualizes before download)
        time.sleep(5)
        
        # Extract table data from the page
        table_data = extract_table_data(driver)
        
        return table_data
        
    except Exception as e:
        print(f"Error during export: {e}")
        driver.save_screenshot("/tmp/export_error.png")
        raise

def extract_table_data(driver):
    """Extract data from the visualized table on the page"""
    print("Extracting table data...")
    
    try:
        # Wait for table to be present
        wait = WebDriverWait(driver, 10)
        table = wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        
        # Extract headers
        headers = []
        header_row = table.find_element(By.TAG_NAME, "thead").find_element(By.TAG_NAME, "tr")
        header_cells = header_row.find_elements(By.TAG_NAME, "th")
        headers = [cell.text.strip() for cell in header_cells]
        
        # Extract rows
        rows_data = []
        tbody = table.find_element(By.TAG_NAME, "tbody")
        rows = tbody.find_elements(By.TAG_NAME, "tr")
        
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            row_data = [cell.text.strip() for cell in cells]
            rows_data.append(row_data)
        
        print(f"Extracted {len(rows_data)} rows with {len(headers)} columns")
        return {"headers": headers, "rows": rows_data}
        
    except Exception as e:
        print(f"Error extracting table data: {e}")
        # If table extraction fails, return empty data
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