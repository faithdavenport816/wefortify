# ReliaTrax to Google Sheets Automation

Automatically exports data from ReliaTrax CRM to Google Sheets daily using modular, reusable scrapers.

## Project Structure

```
wefortify/
├── utils.py                    # Shared utilities for all scrapers
├── scraper.py                  # Treatment Thread Export scraper
├── scraper_template.py         # Template for creating new scrapers
├── requirements.txt            # Python dependencies
├── readme.md                   # This file
└── .github/workflows/
    └── scrape.yaml            # GitHub Actions workflow
```

## Current Scrapers

- **scraper.py**: Treatment Thread Export (01/01/2020 to today)
- **client_daily_summary_export.py**: Client Daily Summary Export (01/01/2022 to today, monthly batches)

## Data Pipeline

After both scrapers complete, **data_cleaner.py** automatically runs to:
1. Read raw exports from Google Sheets
2. Clean and transform the data using the assessment dictionary
3. Generate analytical frames:
   - **long_frame**: Assessment data in long format with imputed values
   - **wide_frame**: Pivoted view with questions as columns
   - **yoy_frame**: Year-over-year metrics with aggregations and program year rollups

## Setup Instructions

### 1. Create GitHub Repository

- Go to GitHub and create a new repository
- Clone it locally or push these files to it

### 2. Configure Sheet IDs

Edit each scraper file and update the `SHEET_ID` constant in the `main()` function with your Google Sheets ID.

Get your Sheet ID from the URL: `https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit`

### 3. Add GitHub Secrets

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

- **RELIATRAX_USERNAME**: Your ReliaTrax login username
- **RELIATRAX_PASSWORD**: Your ReliaTrax login password
- **GOOGLE_SHEETS_CREDS**: The entire contents of your service account JSON file

### 4. Test the Workflow

- Go to Actions tab in your GitHub repo
- Click on "ReliaTrax Daily Export" workflow
- Click "Run workflow" → "Run workflow"
- Watch it run and check your Google Sheet!

## Schedule

The workflow runs automatically every day at 9 AM UTC (4 AM EST / 1 AM PST).

To change the schedule, edit `.github/workflows/scrape.yaml` and modify the cron expression:

- `0 9 * * *` = 9 AM UTC daily
- `0 14 * * *` = 2 PM UTC daily
- `0 */6 * * *` = Every 6 hours

## Creating a New Scraper

### Quick Start

1. **Copy the template**:
   ```bash
   cp scraper_template.py scraper_incidents.py
   ```

2. **Customize the new scraper**:
   - Update the docstring with your scraper name
   - Update the `SHEET_ID` constant in `main()` with your Google Sheets ID
   - Change the URL in `export_data()` to your target page
   - Update element IDs/selectors to match your page
   - Modify form interactions as needed

3. **Add to GitHub Actions** (optional):
   - Edit `.github/workflows/scrape.yaml`
   - Add a new step to run your scraper

### Shared Utilities (utils.py)

All scrapers can use these shared functions:

- `setup_driver()` - Configure Selenium Chrome driver
- `login_to_reliatrax(driver, username, password)` - Handle ReliaTrax login
- `get_sheets_client()` - Get Google Sheets API client
- `write_to_sheets(data, sheet_id, clear_first=True)` - Write data to Google Sheets
- `wait_for_csv_download(download_dir, max_wait)` - Wait for CSV download
- `read_csv_file(file_path)` - Parse CSV file
- `clear_old_csv_files(download_dir)` - Clean up old downloads

### Example: Creating an Incidents Scraper

```python
# scraper_incidents.py
from utils import setup_driver, login_to_reliatrax, write_to_sheets
import os
from datetime import datetime

def export_incidents(driver, start_date, end_date):
    driver.get("https://wefortify.reliatrax.net/Incidents.aspx/Export")
    # ... your page-specific logic ...
    return data

def main():
    SHEET_ID = "your_incidents_sheet_id_here"

    driver = setup_driver()
    login_to_reliatrax(driver, os.environ['RELIATRAX_USERNAME'],
                       os.environ['RELIATRAX_PASSWORD'])
    data = export_incidents(driver, "01/01/2020", datetime.now().strftime("%m/%d/%Y"))
    write_to_sheets(data, SHEET_ID)
```

## Troubleshooting

### If the workflow fails:

1. Go to Actions tab and click on the failed run
2. Download the "debug-files" artifact to see screenshots
3. Check the logs for error messages

### Common Issues

**Login failed**:
- Verify RELIATRAX_USERNAME and RELIATRAX_PASSWORD are correct
- Check if ReliaTrax login page has changed

**Google Sheets error**:
- Verify the service account email has Editor access to your sheet
- Check that GOOGLE_SHEETS_CREDS is the complete JSON file

**Export failed**:
- The page structure may have changed
- Check debug screenshots to see what the scraper is seeing
- Verify element IDs/selectors in your scraper code

## Date Range Configuration

Current default: **01/01/2020 to today**

To change the date range, edit the `main()` function in your scraper:

```python
start_date_str = "01/01/2020"  # Change this
end_date_str = datetime.now().strftime("%m/%d/%Y")
```

## Files

- `utils.py` - Shared utilities for all scrapers
- `scraper.py` - Treatment Thread Export scraper
- `client_daily_summary_export.py` - Client Daily Summary Export scraper
- `data_cleaner.py` - Data cleaning and transformation pipeline
- `scraper_template.py` - Template for creating new scrapers
- `requirements.txt` - Python dependencies
- `.github/workflows/scrape.yaml` - GitHub Actions workflow
- `readme.md` - This file

## Workflow Execution Order

When the workflow runs (daily at 9 AM UTC or manually triggered):

1. **Treatment Thread Export** (`scraper.py`)
   - Exports all treatment thread data from 01/01/2020 to today
   - Writes to `treatment_thread_export` tab

2. **Client Daily Summary Export** (`client_daily_summary_export.py`)
   - Exports client daily activity from 01/01/2022 to today
   - Loops through monthly batches (30-day limit)
   - Writes to `client_summary_export` tab

3. **Data Cleaning Pipeline** (`data_cleaner.py`)
   - Reads raw exports + `assesment_dictionary` tab
   - Cleans, transforms, and generates analytical frames
   - Writes to `long_frame`, `wide_frame`, and `yoy_frame` tabs
