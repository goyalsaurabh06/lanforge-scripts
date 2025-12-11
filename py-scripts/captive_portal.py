from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import logging
import time
import subprocess
import sys



class CaptivePortalHandler:
    def __init__(self, headless=False):
        """
        Initializes the Chrome driver with best-practice options.
        :param headless: Boolean to run Chrome in headless mode (no GUI).
        """
        self.driver = self.setup_driver(headless)
        self.wait = WebDriverWait(self.driver, 10) # Centralized wait
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    def setup_driver(self, headless):
        # 1. Create Options Instance
        options = Options()

        # --- Essential Options ---
        if headless:
            options.add_argument("--headless=new") # Modern headless mode
        
        # ignores certificate errors common in captive portals
        options.add_argument("--ignore-certificate-errors") 
        options.add_argument("--allow-insecure-localhost")
        
        # Starts the browser maximized to avoid responsive layout issues
        options.add_argument("--start-maximized") 
        
        # --- Stability & Performance Options ---
        # Overcomes limited resource problems
        options.add_argument("--disable-dev-shm-usage") 
        # Disables sandbox (sometimes required in Docker/Linux)
        options.add_argument("--no-sandbox") 
        # Disables automation info bar
        options.add_argument("--disable-infobars")

        service = Service() 

        # 3. Instantiate Driver
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    
    def handle_portal(self):
        """
        Navigates to the specified URL and handles captive portal if detected.
        :param url: URL to navigate to.
        """
        self.driver.get("https://google.com")  # Common URL to trigger captive portal
        # time.sleep(100000)
        
        try:
            # Wait for the Connect button to be clickable and click it
            locator = (By.XPATH, "//div[contains(@class, 'atn-button-text') and normalize-space()='Connect']")
            connect_button = self.wait.until(EC.element_to_be_clickable(locator))
            connect_button.click()
            logging.info("Successfully clicked the Connect button.")
            time.sleep(10)

        except Exception as e:
            print("No captive portal detected or an error occurred:", e)
        finally:
            self.driver.quit()
    
    def check_ping(self):
        logging.info("Portal login complete. Verifying internet access...")

        # Since this script is already running inside the VRF, 
        # we use the standard 'ping' directly (no need for vrf_exec here)
        ping_cmd = ["ping", "google.com", "-c", "5"]

        # Run the ping
        # We use check=False because we want to handle the exit manually
        ping_result = subprocess.run(ping_cmd, capture_output=True, text=True)

        if ping_result.returncode == 0:
            print("✅ PING SUCCESS: Internet is reachable.")
            # Exit with 0 so the parent script knows it SUCCEEDED
            sys.exit(0)
        else:
            print(f"❌ PING FAILED: Internet unreachable. Return code: {ping_result.returncode}")
            print(f"Ping Output: {ping_result.stderr}")
            # Exit with 1 so the parent script's 'check=True' catches this as an ERROR
            sys.exit(1)


def main():
    handler = CaptivePortalHandler(headless=True)
    handler.handle_portal()
    handler.check_ping()



    

if __name__ == "__main__":
    main()