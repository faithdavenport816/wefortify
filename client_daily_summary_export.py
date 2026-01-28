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
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

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


def generate_monthly_ranges(start_date, end_date):
    """Generate monthly date ranges between start_date and end_date

    Args:
        start_date: datetime object for start
        end_date: datetime object for end

    Returns:
        List of tuples [(start1, end1), (start2, end2), ...]
    """
    ranges = []
    current = start_date

    while current < end_date:
        # Get the last day of the current month or end_date, whichever is earlier
        next_month = current + relativedelta(months=1)
        month_end = min(next_month - timedelta(days=1), end_date)

        ranges.append((current, month_end))
        current = next_month

    return ranges


def main():
    # Configure your Google Sheet ID and worksheet tab name
    SHEET_ID = "196rg3YfpssRLsdFig4yN9G3U9NrQFPEeROnr1oSNGCA"
    WORKSHEET_NAME = "client_summary_export"

    driver = None

    try:
        # Get credentials from environment
        username = os.environ['RELIATRAX_USERNAME']
        password = os.environ['RELIATRAX_PASSWORD']

        # Setup driver
        driver = setup_driver()

        # Login (reuses shared login function)
        login_to_reliatrax(driver, username, password)

        # Set overall date range - loop through monthly from 2022-01-01 to today
        overall_start = datetime(2022, 1, 1)
        overall_end = datetime.now()

        print(f"Exporting data from {overall_start.strftime('%m/%d/%Y')} to {overall_end.strftime('%m/%d/%Y')}")
        print("This will be done in monthly chunks due to 30-day limit...")

        # Generate monthly date ranges
        monthly_ranges = generate_monthly_ranges(overall_start, overall_end)
        print(f"Total months to process: {len(monthly_ranges)}")

        # Collect all data across all months
        all_headers = None
        all_rows = []

        for i, (month_start, month_end) in enumerate(monthly_ranges, 1):
            start_str = month_start.strftime("%m/%d/%Y")
            end_str = month_end.strftime("%m/%d/%Y")

            print(f"\n[{i}/{len(monthly_ranges)}] Exporting {start_str} to {end_str}...")

            try:
                data = export_data(driver, start_str, end_str)

                if data["rows"]:
                    # Store headers from first successful export
                    if all_headers is None:
                        all_headers = data["headers"]

                    # Add rows to combined data
                    all_rows.extend(data["rows"])
                    print(f"  ✓ Retrieved {len(data['rows'])} rows")
                else:
                    print(f"  - No data for this period")

            except Exception as e:
                print(f"  ✗ Error exporting {start_str} to {end_str}: {e}")
                # Continue with next month instead of failing completely
                continue

        # Write all combined data to Google Sheets
        if all_rows and all_headers:
            combined_data = {
                "headers": all_headers,
                "rows": all_rows
            }

            print(f"\n{'='*60}")
            print(f"Total rows collected: {len(all_rows)}")
            print("Writing combined data to Google Sheets...")
            write_to_sheets(combined_data, SHEET_ID, worksheet_name=WORKSHEET_NAME, clear_first=True)
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
