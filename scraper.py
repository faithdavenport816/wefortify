"""Treatment Thread Export Scraper"""
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


def export_treatment_data(driver, start_date, end_date):
    """Navigate to export page and trigger CSV download"""
    print("Navigating to Treatment Thread Export page...")
    driver.get("https://wefortify.reliatrax.net/TreatmentThread.aspx/ThreadExport")

    try:
        wait = WebDriverWait(driver, 20)

        print("Waiting for export page to load...")
        time.sleep(2)

        # Select "All Folders" from the dropdown
        print("Looking for folder dropdown...")
        folder_dropdown = wait.until(EC.presence_of_element_located((By.ID, "folderID")))
        print("Found folder dropdown, selecting 'All Folders'...")

        select = Select(folder_dropdown)
        select.select_by_value("1")  # Value "1" corresponds to "All Folders"
        print("Selected 'All Folders'")
        time.sleep(1)

        # Set start date
        print(f"Setting start date to {start_date}...")
        start_date_field = wait.until(EC.presence_of_element_located((By.ID, "startDate")))
        start_date_field.clear()
        start_date_field.send_keys(start_date)
        print("Start date set successfully")
        time.sleep(0.5)

        # Set end date
        print(f"Setting end date to {end_date}...")
        end_date_field = driver.find_element(By.ID, "endDate")
        end_date_field.clear()
        end_date_field.send_keys(end_date)
        print("End date set successfully")
        time.sleep(0.5)

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

        # Clear old CSV files and trigger download
        clear_old_csv_files()

        print("Clicking CSV export button to download file...")
        csv_button.click()

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
    WORKSHEET_NAME = "Treatment Thread"  # UPDATE THIS to your tab name

    driver = None

    try:
        # Get credentials from environment
        username = os.environ['RELIATRAX_USERNAME']
        password = os.environ['RELIATRAX_PASSWORD']

        # Setup driver
        driver = setup_driver()

        # Login
        login_to_reliatrax(driver, username, password)

        # Get date range: always from 01/01/2020 to today
        end_date_str = datetime.now().strftime("%m/%d/%Y")
        start_date_str = "01/01/2020"

        print(f"Exporting data from {start_date_str} to {end_date_str}")

        # Export data
        data = export_treatment_data(driver, start_date_str, end_date_str)

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
