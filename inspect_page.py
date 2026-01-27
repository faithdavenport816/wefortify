from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

def inspect_login_page():
    """Inspect the ReliaTrax login page to find correct selectors"""

    # Setup driver (same as your scraper)
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(options=chrome_options)

    try:
        print("Loading login page...")
        driver.get("https://wefortify.reliatrax.net/Account.aspx/Login")

        # Wait for page to load
        time.sleep(3)

        print(f"\nPage Title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        print("\n" + "="*60)

        # Find all input fields
        print("\n📋 ALL INPUT FIELDS:")
        print("="*60)
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for i, inp in enumerate(inputs):
            print(f"\nInput #{i+1}:")
            print(f"  Type: {inp.get_attribute('type')}")
            print(f"  ID: {inp.get_attribute('id')}")
            print(f"  Name: {inp.get_attribute('name')}")
            print(f"  Class: {inp.get_attribute('class')}")
            print(f"  Placeholder: {inp.get_attribute('placeholder')}")

        # Find all buttons
        print("\n\n🔘 ALL BUTTONS:")
        print("="*60)
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for i, btn in enumerate(buttons):
            print(f"\nButton #{i+1}:")
            print(f"  Text: {btn.text}")
            print(f"  ID: {btn.get_attribute('id')}")
            print(f"  Name: {btn.get_attribute('name')}")
            print(f"  Type: {btn.get_attribute('type')}")
            print(f"  Class: {btn.get_attribute('class')}")

        # Also check for input type=submit
        submits = driver.find_elements(By.CSS_SELECTOR, "input[type='submit']")
        if submits:
            print("\n\n✅ SUBMIT INPUTS:")
            print("="*60)
            for i, sub in enumerate(submits):
                print(f"\nSubmit #{i+1}:")
                print(f"  Value: {sub.get_attribute('value')}")
                print(f"  ID: {sub.get_attribute('id')}")
                print(f"  Name: {sub.get_attribute('name')}")

        # Save page source
        print("\n\n💾 Saving page source to inspect_page_source.html...")
        with open("inspect_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        # Save screenshot
        print("📸 Saving screenshot to inspect_page.png...")
        driver.save_screenshot("inspect_page.png")

        print("\n✅ Inspection complete!")
        print("Check inspect_page_source.html and inspect_page.png for details")

    finally:
        driver.quit()

if __name__ == '__main__':
    inspect_login_page()
