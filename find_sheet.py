import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Setup Google Sheets API
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

creds_dict = json.loads(os.environ['GOOGLE_SHEETS_CREDS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# List all spreadsheets accessible to this service account
print("Spreadsheets accessible to your service account:")
print("=" * 80)

try:
    spreadsheets = client.openall()
    for i, sheet in enumerate(spreadsheets, 1):
        print(f"\n{i}. {sheet.title}")
        print(f"   ID: {sheet.id}")
        print(f"   URL: https://docs.google.com/spreadsheets/d/{sheet.id}/edit")

        # Check if this matches the SHEET_ID in secrets
        if sheet.id == os.environ.get('SHEET_ID'):
            print("   ⭐ THIS IS THE ONE! (matches SHEET_ID secret)")

except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 80)
print("\nThe sheet with ⭐ is where your data is being exported!")
