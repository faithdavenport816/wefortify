ReliaTrax to Google Sheets Automation
Automatically exports treatment thread data from ReliaTrax CRM to Google Sheets daily.
Setup Instructions
1. Create GitHub Repository

Go to GitHub and create a new repository
Clone it locally or push these files to it

2. Add GitHub Secrets
Go to your repository → Settings → Secrets and variables → Actions → New repository secret
Add the following secrets:

RELIATRAX_USERNAME: Your ReliaTrax login username
RELIATRAX_PASSWORD: Your ReliaTrax login password
GOOGLE_SHEETS_CREDS: The entire contents of your service account JSON file
SHEET_ID: 1eB7htWvk6y2Naw500KzstmXSpkMpgyu0VbkR8Sayh-8

3. Test the Workflow

Go to Actions tab in your GitHub repo
Click on "ReliaTrax Daily Export" workflow
Click "Run workflow" → "Run workflow"
Watch it run and check your Google Sheet!

Schedule
The workflow runs automatically every day at 9 AM UTC (4 AM EST / 1 AM PST).
To change the schedule, edit .github/workflows/scrape.yml and modify the cron expression:

0 9 * * * = 9 AM UTC daily
0 14 * * * = 2 PM UTC daily
0 */6 * * * = Every 6 hours

Troubleshooting
If the workflow fails:

Go to Actions tab and click on the failed run
Download the "debug-screenshots" artifact to see what went wrong
Check the logs for error messages

Common Issues
Login failed:

Verify RELIATRAX_USERNAME and RELIATRAX_PASSWORD are correct
Check if ReliaTrax login page has changed

Google Sheets error:

Verify the service account email has Editor access to your sheet
Check that GOOGLE_SHEETS_CREDS is the complete JSON file

Table extraction failed:

The page structure may have changed
Check debug screenshots to see what the scraper is seeing

Files

scraper.py - Main scraper script
requirements.txt - Python dependencies
.github/workflows/scrape.yml - GitHub Actions workflow
README.md - This file