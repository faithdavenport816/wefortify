"""
TEMPLATE: Copy this file to create a new scraper

Instructions:
1. Copy this file to a new name (e.g., scraper_incidents.py)
2. Update the docstring at the top with the scraper name
3. Update the URL in export_data() function
4. Customize the export_data() function to interact with your specific page
5. Update main() to use the correct environment variables for SHEET_ID
6. Add your scraper to the GitHub Actions workflow if needed

Example naming:
- scraper_treatment.py - Treatment Thread Export (current scraper.py)
- scraper_incidents.py - Incidents Export
- scraper_inventory.py - Inventory Export
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import os
import time
from datetime import datetime

from utils import (
    setup_driver,
    login_to_reliatrax,
    write_to_sheets,
    wait_for_csv_download,
    read_csv_file,
    clear_old_csv_files
)


def export_data(driver, start_date, end_date):
    """
    Navigate to export page and trigger CSV download

    CUSTOMIZE THIS FUNCTION for your specific export page:
    - Update the URL to your export page
    - Update element IDs/selectors to match your page
    - Add/remove form interactions as needed
    """
    print("Navigating to export page...")
    driver.get("https://wefortify.reliatrax.net/Report.aspx/ClientDailyActivity")

    try:
        wait = WebDriverWait(driver, 20)

        print("Waiting for export page to load...")
        time.sleep(2)

        # EXAMPLE: Select dropdown - customize as needed
        # print("Looking for dropdown...")
        # dropdown = wait.until(EC.presence_of_element_located((By.ID, "yourDropdownId")))
        # select = Select(dropdown)
        # select.select_by_value("1")
        # time.sleep(1)

        # Set start date (if your page has date fields)
        print(f"Setting start date to {start_date}...")
        start_date_field = wait.until(EC.presence_of_element_located((By.ID, "dayDateStart")))
        start_date_field.clear()
        start_date_field.send_keys(start_date)
        print("Start date set successfully")
        time.sleep(0.5)

        # Set end date (if your page has date fields)
        print(f"Setting end date to {end_date}...")
        end_date_field = driver.find_element(By.ID, "dayDateEnd")
        end_date_field.clear()
        end_date_field.send_keys(end_date)
        print("End date set successfully")
        time.sleep(0.5)

        # Click the GO button to submit the date range
        print("Looking for GO button...")
        go_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='submit'][value='GO']")))
        print("Found GO button, clicking...")
        go_button.click()
        time.sleep(2)  # Wait for results to load

        # Clear old CSV files before download
        clear_old_csv_files()

        # Find and click the export button - UPDATE THE ID
        print("Looking for export button...")
        export_button = wait.until(EC.presence_of_element_located((By.ID, "downloadCSVLinkID")))
        print("Found export button, clicking...")
        export_button.click()

        # Wait for file to download
        downloaded_file = wait_for_csv_download()

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


def main():
    # Configure your Google Sheet ID and worksheet tab name
    SHEET_ID = "196rg3YfpssRLsdFig4yN9G3U9NrQFPEeROnr1oSNGCA"
    WORKSHEET_NAME = "Client Daily Summary"  # UPDATE THIS to your tab name

    driver = None

    try:
        # Get credentials from environment
        username = os.environ['RELIATRAX_USERNAME']
        password = os.environ['RELIATRAX_PASSWORD']

        # Setup driver
        driver = setup_driver()

        # Login (reuses shared login function)
        login_to_reliatrax(driver, username, password)

        # Set date range (customize as needed)
        end_date_str = datetime.now().strftime("%m/%d/%Y")
        start_date_str = "01/01/2026"  # Or customize your date range

        print(f"Exporting data from {start_date_str} to {end_date_str}")

        # Export data
        data = export_data(driver, start_date_str, end_date_str)

        if data["rows"]:
            # Write to Google Sheets - specify worksheet name to write to specific tab
            write_to_sheets(data, SHEET_ID, worksheet_name=WORKSHEET_NAME, clear_first=True)
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
