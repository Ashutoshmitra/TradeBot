from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time
import csv
import os
import argparse

def setup_driver(headless=True):
    """Set up the Chrome WebDriver with appropriate options for containerized environment."""
    options = webdriver.ChromeOptions()
    
    # Only enable headless mode if specified
    if headless:
        options.add_argument('--headless')
    
    # Core options for stability
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--start-maximized')
    options.add_argument('--window-size=1920,1080')
    
    # Performance options
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-logging')
    options.add_argument('--disable-notifications')
    options.add_argument('--enable-javascript')
    
    # User agent
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    # Use a normal page load strategy
    options.page_load_strategy = 'normal'
    
    # Initialize the driver
    driver = webdriver.Chrome(options=options)
    
    # Set page load timeout
    driver.set_page_load_timeout(60)
    
    return driver

def get_dropdown_options(driver, input_id):
    """Retrieve all available options from a dropdown."""
    try:
        # Wait for dropdown to be clickable
        dropdown = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, input_id))
        )
        # Scroll to dropdown
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
        # Click to open dropdown
        dropdown.click()
        time.sleep(1)
        
        # Get all options
        options = driver.find_elements(By.CSS_SELECTOR, f"div[id^='{input_id.replace('input', 'option')}-']")
        option_texts = [option.text.strip() for option in options if option.text.strip()]
        
        # Close dropdown by clicking again
        dropdown.click()
        time.sleep(0.5)
        return option_texts
    except Exception as e:
        print(f"Error getting options for {input_id}: {e}")
        return []

def select_dropdown_option(driver, input_id, option_index, wait):
    """Select an option from a dropdown by index."""
    try:
        print(f"Selecting option {option_index} from dropdown {input_id}")
        
        # Click dropdown to open it
        dropdown = wait.until(EC.element_to_be_clickable((By.ID, input_id)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
        dropdown.click()
        time.sleep(1)
        
        # Click the specific option
        option_selector = f"//div[@id='{input_id.replace('input', 'option')}-{option_index}']"
        option = wait.until(EC.element_to_be_clickable((By.XPATH, option_selector)))
        option_text = option.text.strip()
        option.click()
        
        print(f"Selected option: {option_text}")
        return option_text
    except Exception as e:
        print(f"Selection failed: {e}")
        
        # JavaScript fallback approach
        try:
            print("Trying JavaScript approach...")
            driver.execute_script(f"""
                var dropdown = document.getElementById('{input_id}');
                if (dropdown) {{
                    dropdown.scrollIntoView({{block: 'center'}});
                    dropdown.click();
                    setTimeout(() => {{
                        var option = document.querySelector('div[id="{input_id.replace("input", "option")}-{option_index}"]');
                        if (option) {{
                            var optionText = option.textContent.trim();
                            option.click();
                            return optionText;
                        }}
                    }}, 1000);
                }}
            """)
            time.sleep(2)
            return ""  # Can't reliably get text with JS approach
        except Exception as js_error:
            print(f"JavaScript approach failed: {js_error}")
            return ""

def scrape_device_list(output_file):
    """Main function to scrape available device brands and models."""
    device_types = ["Smartphone", "Tablet"]
    source = "SG_RV_Source1"
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
    
    # Initialize CSV file with headers
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(['Brand', 'Model', 'Source'])
    
    # Setup driver
    driver = setup_driver(headless=True)
    ignored_exceptions = (NoSuchElementException, StaleElementReferenceException)
    wait = WebDriverWait(driver, 15, 0.5, ignored_exceptions=ignored_exceptions)
    
    try:
        # Process each device type
        for device_type in device_types:
            print(f"\n========== Processing {device_type} ==========\n")
            
            # Navigate to website
            driver.get("https://compasiatradeinsg.com/tradein/sell")
            
            # Click on device type card
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, f"//div[contains(@class, 'card-button-footer') and text()='{device_type}']")
            )).click()
            time.sleep(2)
            
            # Get all brand options
            brand_options = get_dropdown_options(driver, "react-select-2-input")
            print(f"Found {len(brand_options)} brands for {device_type}: {brand_options}")
            
            device_list = []  # List to hold all discovered devices
            
            # Iterate through each brand
            for brand_idx, brand_name in enumerate(brand_options):
                print(f"\nProcessing brand: {brand_name} (index {brand_idx})")
                
                # Navigate back to main page for each brand
                driver.get("https://compasiatradeinsg.com/tradein/sell")
                wait.until(EC.element_to_be_clickable(
                    (By.XPATH, f"//div[contains(@class, 'card-button-footer') and text()='{device_type}']")
                )).click()
                time.sleep(2)
                
                # Select the brand
                selected_brand = select_dropdown_option(driver, "react-select-2-input", brand_idx, wait)
                if not selected_brand:
                    selected_brand = brand_name  # Fallback to list name if selection fails
                time.sleep(2)
                
                # Get models for this brand
                model_options = get_dropdown_options(driver, "react-select-3-input")
                print(f"Found {len(model_options)} models for {selected_brand}: {model_options}")
                
                # Save each model to our list
                for model_name in model_options:
                    device_list.append([selected_brand, model_name, source])
            
            # Write all devices to CSV
            with open(output_file, 'a', newline='', encoding='utf-8') as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerows(device_list)
            
            print(f"Added {len(device_list)} devices for {device_type} to {output_file}")
    
    except Exception as e:
        print(f"Error in main process: {e}")
    finally:
        driver.quit()
        print("Browser closed. Process complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape available device brands and models')
    parser.add_argument('-o', '--output', type=str, help='Output CSV file path', 
                        default=os.path.join(os.environ.get("OUTPUT_DIR", "output"), "device_list.csv"))
    args = parser.parse_args()
    
    scrape_device_list(args.output)