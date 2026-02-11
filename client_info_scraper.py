"""Client Information Scraper - Scrapes client details from ReliaTrax

This scraper extracts unique ClientIDs from the treatment_thread data
(already loaded by data_cleaner) and scrapes contact info from each client's page.
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time
import re

from utils import (
    setup_driver,
    login_to_reliatrax,
    get_sheets_client,
)


# Configuration
SHEET_ID = "196rg3YfpssRLsdFig4yN9G3U9NrQFPEeROnr1oSNGCA"
OUTPUT_WORKSHEET = "client_info_export"


def get_unique_client_ids_from_treatment_thread(treatment_thread):
    """Extract unique ClientIDs from treatment_thread data (already in memory)

    Args:
        treatment_thread: List of lists with headers in first row, containing ClientID column
    """
    print("Extracting unique ClientIDs from treatment_thread data...")

    if len(treatment_thread) < 2:
        print("No data found in treatment_thread")
        return []

    headers = treatment_thread[0]
    client_id_col = headers.index('ClientID')

    client_ids = set()
    for row in treatment_thread[1:]:
        client_id = row[client_id_col]
        if client_id:
            client_ids.add(client_id)

    unique_ids = sorted(list(client_ids))
    print(f"Found {len(unique_ids)} unique ClientIDs")
    return unique_ids


def scrape_client_info(driver, client_id):
    """Scrape client information page for a given ClientID

    URL pattern: https://wefortify.reliatrax.net/TreatmentMaster.aspx/TreatmentMaster/{clientID}
    """
    url = f"https://wefortify.reliatrax.net/TreatmentMaster.aspx/TreatmentMaster/{client_id}"

    print(f"  Navigating to client page: {client_id}")
    driver.get(url)

    try:
        wait = WebDriverWait(driver, 10)
        time.sleep(2)  # Allow page to fully render

        # Initialize result with ClientID
        result = {
            'ClientID': client_id,
            'Name': '',
            'DOB': '',
            'Nickname': '',
            'PhoneNumber': '',
            'Email': ''
        }

        # Wait for the Client fieldset to load
        wait.until(EC.presence_of_element_located((By.ID, "ClientHeaderBox")))

        # Extract name from the bold span inside ClientHeaderBox
        # HTML: <span class="bold">Mijares, Aliyah (5/1/2007) "Zinx"</span>
        try:
            name_span = driver.find_element(By.CSS_SELECTOR, "#ClientHeaderBox span.bold")
            name_text = name_span.text

            # Parse: "Mijares, Aliyah (5/1/2007) "Zinx""
            # Pattern: Name (DOB) "Nickname" or Name (DOB)
            name_match = re.match(r'^([^(]+)\s*\(([^)]+)\)\s*(?:"([^"]+)")?', name_text)
            if name_match:
                result['Name'] = name_match.group(1).strip()
                result['DOB'] = name_match.group(2).strip()
                result['Nickname'] = name_match.group(3) or ''
            else:
                result['Name'] = name_text.strip()
        except Exception as e:
            print(f"    Warning: Could not find name element: {e}")

        # Extract phone number
        # HTML: Phone Number: <strong>719-214-5339</strong>
        try:
            page_source = driver.page_source

            # Look for phone number pattern in page source
            phone_match = re.search(
                r'Phone Number:\s*<strong>([^<]+)</strong>',
                page_source
            )
            if phone_match:
                result['PhoneNumber'] = phone_match.group(1).strip()
        except Exception as e:
            print(f"    Warning: Could not find phone number: {e}")

        # Extract email
        # HTML: Email: <strong><a ... href="mailto:zinxmijares@gmail.com">zinxmijares@gmail.com</a></strong>
        try:
            email_match = re.search(
                r'Email:\s*<strong><a[^>]*>([^<]+)</a></strong>',
                page_source
            )
            if email_match:
                result['Email'] = email_match.group(1).strip()
            else:
                # Fallback: email without link
                email_match2 = re.search(
                    r'Email:\s*<strong>([^<]+)</strong>',
                    page_source
                )
                if email_match2:
                    result['Email'] = email_match2.group(1).strip()
        except Exception as e:
            print(f"    Warning: Could not find email: {e}")

        print(f"    Scraped: {result['Name']} | {result['PhoneNumber']} | {result['Email']}")
        return result

    except Exception as e:
        print(f"    Error scraping client {client_id}: {e}")
        return {
            'ClientID': client_id,
            'Name': '',
            'DOB': '',
            'Nickname': '',
            'PhoneNumber': '',
            'Email': '',
            'Error': str(e)
        }


def write_client_info_to_sheets(client, results):
    """Write scraped client info to Google Sheets"""
    print(f"\nWriting {len(results)} client records to {OUTPUT_WORKSHEET}...")

    spreadsheet = client.open_by_key(SHEET_ID)

    # Try to get existing worksheet, or create it
    try:
        worksheet = spreadsheet.worksheet(OUTPUT_WORKSHEET)
        worksheet.clear()
    except:
        worksheet = spreadsheet.add_worksheet(
            title=OUTPUT_WORKSHEET,
            rows=len(results) + 1,
            cols=6
        )

    # Prepare data
    headers = ['ClientID', 'Name', 'DOB', 'Nickname', 'PhoneNumber', 'Email']
    rows = [headers]

    for result in results:
        rows.append([
            result.get('ClientID', ''),
            result.get('Name', ''),
            result.get('DOB', ''),
            result.get('Nickname', ''),
            result.get('PhoneNumber', ''),
            result.get('Email', '')
        ])

    worksheet.update('A1', rows, value_input_option='USER_ENTERED')
    print(f"Successfully wrote {len(results)} records to {OUTPUT_WORKSHEET}")


def scrape_all_clients(treatment_thread):
    """Main function to scrape all clients from treatment_thread data

    This can be called from data_cleaner.py with the treatment_thread data
    already loaded, avoiding a separate sheet read.

    Args:
        treatment_thread: List of lists (with headers) from treatment_thread_export
    """
    print("="*60)
    print("Client Information Scraper")
    print("="*60)

    driver = None

    try:
        # Get credentials from environment
        username = os.environ['RELIATRAX_USERNAME']
        password = os.environ['RELIATRAX_PASSWORD']

        # Extract unique client IDs from treatment_thread data
        client_ids = get_unique_client_ids_from_treatment_thread(treatment_thread)

        if not client_ids:
            print("No client IDs found to process")
            return []

        # Setup browser and login
        print("\nSetting up browser...")
        driver = setup_driver()
        login_to_reliatrax(driver, username, password)

        # Scrape each client
        print(f"\nScraping {len(client_ids)} clients...")
        results = []

        for i, client_id in enumerate(client_ids):
            print(f"\n[{i+1}/{len(client_ids)}] Processing ClientID: {client_id}")
            result = scrape_client_info(driver, client_id)
            results.append(result)

            # Small delay to avoid overwhelming the server
            time.sleep(0.5)

        # Write results to Google Sheets
        sheets_client = get_sheets_client()
        write_client_info_to_sheets(sheets_client, results)

        print("\n" + "="*60)
        print("Client Information Scraper completed!")
        print("="*60)

        return results

    except Exception as e:
        print(f"Error in scraper execution: {e}")
        raise

    finally:
        if driver:
            driver.quit()
            print("Browser closed.")


def main():
    """Standalone execution - reads treatment_thread from Google Sheets"""
    print("Running in standalone mode - fetching treatment_thread from Sheets...")

    # Get Google Sheets client and fetch treatment_thread data
    sheets_client = get_sheets_client()
    spreadsheet = sheets_client.open_by_key(SHEET_ID)
    worksheet = spreadsheet.worksheet("treatment_thread_export")
    treatment_thread = worksheet.get_all_values()

    # Run the scraper
    scrape_all_clients(treatment_thread)


if __name__ == '__main__':
    main()
