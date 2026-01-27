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

        # Save page source for debugging
        page_source = driver.page_source
        print(f"Page title: {driver.title}")
        print(f"Current URL: {driver.current_url}")

        # Try multiple selectors for username field
        username_field = None
        username_selectors = [
            (By.ID, "txtUsername"),
            (By.NAME, "username"),
            (By.NAME, "txtUsername"),
            (By.CSS_SELECTOR, "input[type='text']"),
            (By.CSS_SELECTOR, "input[name*='user' i]"),
            (By.XPATH, "//input[@type='text']"),
        ]

        for selector_type, selector_value in username_selectors:
            try:
                print(f"Trying selector: {selector_type} = {selector_value}")
                username_field = wait.until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                print(f"Found username field with: {selector_type} = {selector_value}")
                break
            except TimeoutException:
                continue

        if not username_field:
            print("Could not find username field with any selector!")
            print(f"Saving page source to /tmp/page_source.html")
            with open("/tmp/page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            raise TimeoutException("Username field not found with any selector")

        username_field.clear()
        username_field.send_keys(username)
        print("Username entered successfully")

        # Find and fill password field
        password_field = None
        password_selectors = [
            (By.ID, "txtPassword"),
            (By.NAME, "password"),
            (By.NAME, "txtPassword"),
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.XPATH, "//input[@type='password']"),
        ]

        for selector_type, selector_value in password_selectors:
            try:
                password_field = driver.find_element(selector_type, selector_value)
                print(f"Found password field with: {selector_type} = {selector_value}")
                break
            except:
                continue

        if not password_field:
            raise TimeoutException("Password field not found")

        password_field.clear()
        password_field.send_keys(password)
        print("Password entered successfully")

        # Click login button
        login_button = None
        login_button_selectors = [
            (By.ID, "btnLogin"),
            (By.NAME, "btnLogin"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.CSS_SELECTOR, "input[type='submit']"),
            (By.XPATH, "//button[contains(text(), 'Login') or contains(text(), 'Sign In')]"),
            (By.XPATH, "//input[@type='submit']"),
        ]

        for selector_type, selector_value in login_button_selectors:
            try:
                login_button = driver.find_element(selector_type, selector_value)
                print(f"Found login button with: {selector_type} = {selector_value}")
                break
            except:
                continue

        if not login_button:
            raise TimeoutException("Login button not found")

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