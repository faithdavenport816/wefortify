from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

def inspect_export_page():
    """Inspect the ReliaTrax export page to find correct selectors"""

    # Setup driver
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(options=chrome_options)

    try:
        # First login
        print("Logging in...")
        username = os.environ.get('RELIATRAX_USERNAME', 'test')
        password = os.environ.get('RELIATRAX_PASSWORD', 'test')

        driver.get("https://wefortify.reliatrax.net/Account.aspx/Login")
        time.sleep(2)

        # Quick login (assuming we know the selectors work now)
        wait = WebDriverWait(driver, 15)
        username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']")))
        username_field.send_keys(username)

        password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        password_field.send_keys(password)

        login_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
        login_button.click()

        time.sleep(3)
        print("Logged in successfully!")

        # Now navigate to export page
        print("\nNavigating to export page...")
        driver.get("https://wefortify.reliatrax.net/TreatmentThread.aspx/ThreadExport")
        time.sleep(3)

        print(f"\nPage Title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        print("\n" + "="*60)

        # Find all checkboxes
        print("\n☑️  ALL CHECKBOXES:")
        print("="*60)
        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        for i, cb in enumerate(checkboxes):
            print(f"\nCheckbox #{i+1}:")
            print(f"  ID: {cb.get_attribute('id')}")
            print(f"  Name: {cb.get_attribute('name')}")
            print(f"  Class: {cb.get_attribute('class')}")
            print(f"  Checked: {cb.is_selected()}")
            print(f"  Value: {cb.get_attribute('value')}")

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

        # Find all input buttons
        print("\n\n📝 ALL INPUT BUTTONS:")
        print("="*60)
        input_buttons = driver.find_elements(By.CSS_SELECTOR, "input[type='button'], input[type='submit']")
        for i, inp in enumerate(input_buttons):
            print(f"\nInput Button #{i+1}:")
            print(f"  Value: {inp.get_attribute('value')}")
            print(f"  ID: {inp.get_attribute('id')}")
            print(f"  Name: {inp.get_attribute('name')}")

        # Save page source
        print("\n\n💾 Saving export page source...")
        with open("inspect_export_page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        # Save screenshot
        print("📸 Saving screenshot...")
        driver.save_screenshot("inspect_export_page.png")

        print("\n✅ Inspection complete!")
        print("Check inspect_export_page_source.html and inspect_export_page.png")

    except Exception as e:
        print(f"Error: {e}")
        driver.save_screenshot("inspect_export_error.png")
        with open("inspect_export_error.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    finally:
        driver.quit()

if __name__ == '__main__':
    inspect_export_page()
