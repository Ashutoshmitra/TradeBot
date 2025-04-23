import argparse
import time
import logging
import os
import re
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_arguments():
    parser = argparse.ArgumentParser(description='...')
    parser.add_argument('-n', '--num_devices', type=int, default=0, 
                        help='Number of devices to scrape. 0 means scrape all devices (default: 0)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')    
    return parser.parse_args()

def setup_driver(debug=False):
    chrome_options = Options()
    if not debug:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def get_device_list(driver, limit=None):
    driver.get("https://sellto.carousell.sg/")
    time.sleep(2)
    
    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[id^='react-select-'][type='text']"))
        )
        
        search_box.send_keys(" ")
        time.sleep(1)
        
        device_options = driver.find_elements(By.XPATH, "//div[contains(@id, 'react-select-') and contains(@class, 'option')]")
        if not device_options:
            logger.error("No device options found")
            return []
        
        logger.info(f"Found {len(device_options)} device options")
        
        devices = []
        for option in device_options:
            try:
                device_name = option.text
                device_id = option.get_attribute('id')
                
                if device_name and device_name.strip():
                    device_type = "Smartphone"
                    if "ipad" in device_name.lower() or "tab" in device_name.lower():
                        device_type = "Tablet"
                    
                    brand = "Unknown"
                    if "apple" in device_name.lower() or "iphone" in device_name.lower() or "ipad" in device_name.lower():
                        brand = "Apple"
                    elif "samsung" in device_name.lower():
                        brand = "Samsung"
                    elif "xiaomi" in device_name.lower():
                        brand = "Xiaomi"
                    elif "oppo" in device_name.lower():
                        brand = "OPPO"
                    elif "google" in device_name.lower():
                        brand = "Google"
                    
                    logger.info(f"Found device: {device_name}")
                    devices.append({
                        'name': device_name,
                        'id': device_id,
                        'type': device_type,
                        'brand': brand
                    })
            except Exception:
                continue
        
        if limit and len(devices) > limit:
            devices = devices[:limit]
        
        return devices
    
    except Exception as e:
        logger.error(f"Error getting device list: {e}")
        return []

def select_device(driver, device):
    driver.get("https://sellto.carousell.sg/")
    time.sleep(2)
    
    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[id^='react-select-'][type='text']"))
        )
        
        search_box.send_keys(device['name'])
        time.sleep(1)
        search_box.send_keys(Keys.ENTER)
        logger.info(f"Selected device: {device['name']}")
        
        time.sleep(3)
        return True
        
    except Exception as e:
        logger.error(f"Error selecting device: {e}")
        return False

def handle_condition_form(driver, condition):
    try:
        logger.info(f"Handling form for condition: {condition}")
        time.sleep(2)
        
        # 1. Physical Condition
        physical_conditions = {
            "Perfect": "No scratches, defects or dent at all",
            "Good": "3 to 5 micro scratches of less than 3mm",
            "Fair": "Has dents, cracks or gaps in the casing"
        }
        
        physical_condition_elements = driver.find_elements(By.CSS_SELECTOR, "div.border.rounded-2xl.border-gray-200.transition-all")
        
        for element in physical_condition_elements:
            condition_text = element.find_element(By.TAG_NAME, "h5").text
            if condition_text == physical_conditions[condition]:
                driver.execute_script("arguments[0].click();", element)
                logger.info(f"Selected physical condition: {condition_text}")
                break
        
        time.sleep(1)
        
        # 2. Screen Condition - select "Flawless or good as new"
        screen_condition_elements = driver.find_elements(By.CSS_SELECTOR, "div.border.rounded-2xl.border-gray-200.transition-all")
        for element in screen_condition_elements:
            condition_text = element.find_element(By.TAG_NAME, "h5").text
            if condition_text == "Flawless or good as new":
                driver.execute_script("arguments[0].click();", element)
                logger.info("Selected Flawless screen condition")
                break
        
        time.sleep(1)
        
        # 3. Display Condition - select "Flawless or as good as new"
        display_condition_elements = driver.find_elements(By.CSS_SELECTOR, "div.border.rounded-2xl.border-gray-200.transition-all")
        for element in display_condition_elements:
            condition_text = element.find_element(By.TAG_NAME, "h5").text
            if condition_text == "Flawless or as good as new":
                driver.execute_script("arguments[0].click();", element)
                logger.info("Selected Flawless display condition")
                break
        
        time.sleep(1)
        
        # 4. Battery Health - select "91 – 100 %"
        battery_condition_elements = driver.find_elements(By.CSS_SELECTOR, "div.border.rounded-2xl.border-gray-200.transition-all")
        for element in battery_condition_elements:
            condition_text = element.find_element(By.TAG_NAME, "h5").text
            if condition_text == "91 – 100 %":
                driver.execute_script("arguments[0].click();", element)
                logger.info("Selected 91-100% battery health")
                break
        
        time.sleep(1)
        
        # 5. Functional Issues - select "No"
        functional_elements = driver.find_elements(By.CSS_SELECTOR, "input[name='other_issue']")
        for element in functional_elements:
            if element.get_attribute("value") == "no":
                driver.execute_script("arguments[0].click();", element)
                logger.info("Selected No functional issues")
                break
        
        time.sleep(1)
        
        # Wait for Next button to be clickable
        try:
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.button.inline-flex:not([disabled])"))
            )
            driver.execute_script("arguments[0].click();", next_button)
            logger.info("Clicked Next button")
            time.sleep(5)  # Increased wait for page load
            return True
        except TimeoutException:
            logger.error("Next button not clickable within timeout")
            return False
        
    except Exception as e:
        logger.error(f"Error handling condition form: {e}")
        return False

def extract_trade_in_value(driver):
    try:
        # Wait for trade-in value to be present
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//p[contains(text(), 'S$')]"))
        )
        
        price_elements = driver.find_elements(By.XPATH, "//p[contains(text(), 'S$')]")
        
        for element in price_elements:
            text = element.text
            if "S$" in text:
                match = re.search(r'S\$\s*(\d+)', text)
                if match:
                    value = match.group(1)
                    logger.info(f"Extracted trade-in value: {value}")
                    return value
        
        price_elements = driver.find_elements(By.XPATH, "//p[contains(text(), '$')]")
        for element in price_elements:
            text = element.text
            if "$" in text:
                match = re.search(r'\$\s*(\d+)', text)
                if match:
                    value = match.group(1)
                    logger.info(f"Extracted trade-in value: {value}")
                    return value
        
        logger.warning("Could not find trade-in value")
        return "Not found"
    
    except Exception as e:
        logger.error(f"Error extracting trade-in value: {e}")
        return "Error"

def save_results(results, filename='carousell_trade_in_values.xlsx'):
    if not results:
        logger.warning("No results to save")
        return
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        df = pd.DataFrame(results)
        output_path = os.path.join(output_dir, filename)
        
        if os.path.exists(output_path):
            existing_df = pd.read_excel(output_path)
            df = pd.concat([existing_df, df], ignore_index=True)
        
        df.to_excel(output_path, index=False)
        logger.info(f"Results saved to {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving results: {e}")

def process_storage_options(driver, device):
    trade_in_results = []
    
    try:
        # Get all storage options first
        storage_options = driver.find_elements(By.CSS_SELECTOR, 
            "div.py-\\[0\\.5rem\\].px-3.md\\:px-5.bg-white.rounded-xl.border.flex.cursor-pointer, div.rounded-xl.border.flex.cursor-pointer")
        
        if not storage_options:
            logger.error(f"No storage options found for {device['name']}")
            return trade_in_results
        
        # Store the text values of all storage options
        storage_texts = []
        for option in storage_options:
            storage_text = option.text.strip()
            if storage_text:
                storage_texts.append(storage_text)
        
        logger.info(f"Found {len(storage_texts)} storage options")
        
        # Process each storage option
        for i, storage_text in enumerate(storage_texts):
            logger.info(f"Processing storage: {storage_text}")
            
            # For each storage option, we need to start fresh
            driver.get("https://sellto.carousell.sg/")
            time.sleep(2)
            
            # Select the device
            if not select_device(driver, device):
                logger.error(f"Failed to select device: {device['name']}")
                continue
            
            # Get fresh storage options
            storage_options = driver.find_elements(By.CSS_SELECTOR, 
                "div.py-\\[0\\.5rem\\].px-3.md\\:px-5.bg-white.rounded-xl.border.flex.cursor-pointer, div.rounded-xl.border.flex.cursor-pointer")
            
            # Find and click the storage option with matching text
            storage_selected = False
            for option in storage_options:
                if option.text.strip() == storage_text:
                    driver.execute_script("arguments[0].click();", option)
                    storage_selected = True
                    logger.info(f"Selected storage: {storage_text}")
                    break
            
            if not storage_selected:
                logger.error(f"Could not find storage option: {storage_text}")
                continue
            
            # Click Next
            time.sleep(2)
            next_buttons = driver.find_elements(By.TAG_NAME, "button")
            next_clicked = False
            for button in next_buttons:
                if "Next" in button.text:
                    driver.execute_script("arguments[0].click();", button)
                    logger.info("Clicked Next button")
                    next_clicked = True
                    break
            
            if not next_clicked:
                logger.error("Failed to click Next button")
                continue
            
            time.sleep(3)
            
            # Process each condition
            conditions = ["Perfect", "Good", "Fair"]
            for condition in conditions:
                if handle_condition_form(driver, condition):
                    value = extract_trade_in_value(driver)
                    
                    trade_in_results.append({
                        'Country': 'Singapore',
                        'Device Type': device['type'],
                        'Brand': device['brand'],
                        'Model': device['name'],
                        'Capacity': storage_text,
                        'Color': '',
                        'Launch RRP': '',
                        'Condition': condition,
                        'Value Type': 'Trade-in',
                        'Currency': 'SGD',
                        'Value': value,
                        'Source': 'SG_RV_Source6',
                        'Updated on': datetime.now().strftime('%Y-%m-%d'),
                        'Updated by': '',
                        'Comments': ''
                    })
                    
                    logger.info(f"Added result: {device['name']} ({storage_text}) in {condition} condition: {value}")
                    
                    save_results(trade_in_results[-1:])
                    
                    # After processing each condition, start fresh for the next condition
                    driver.get("https://sellto.carousell.sg/")
                    time.sleep(2)
                    
                    # Reselect device
                    if not select_device(driver, device):
                        logger.error(f"Failed to reselect device: {device['name']}")
                        break
                    
                    # Reselect storage
                    storage_options = driver.find_elements(By.CSS_SELECTOR, 
                        "div.py-\\[0\\.5rem\\].px-3.md\\:px-5.bg-white.rounded-xl.border.flex.cursor-pointer, div.rounded-xl.border.flex.cursor-pointer")
                    
                    storage_selected = False
                    for option in storage_options:
                        if option.text.strip() == storage_text:
                            driver.execute_script("arguments[0].click();", option)
                            storage_selected = True
                            break
                    
                    if not storage_selected:
                        logger.error(f"Could not find storage option: {storage_text}")
                        break
                    
                    # Click Next
                    time.sleep(2)
                    next_buttons = driver.find_elements(By.TAG_NAME, "button")
                    for button in next_buttons:
                        if "Next" in button.text:
                            driver.execute_script("arguments[0].click();", button)
                            break
                    time.sleep(3)
                else:
                    logger.error(f"Failed to handle condition: {condition}")
                    # Reset and try the next condition
                    driver.get("https://sellto.carousell.sg/")
                    time.sleep(2)
                    if not select_device(driver, device):
                        break
                    
                    storage_options = driver.find_elements(By.CSS_SELECTOR, 
                        "div.py-\\[0\\.5rem\\].px-3.md\\:px-5.bg-white.rounded-xl.border.flex.cursor-pointer, div.rounded-xl.border.flex.cursor-pointer")
                    
                    storage_selected = False
                    for option in storage_options:
                        if option.text.strip() == storage_text:
                            driver.execute_script("arguments[0].click();", option)
                            storage_selected = True
                            break
                    
                    if not storage_selected:
                        logger.error(f"Could not find storage option: {storage_text}")
                        break
                    
                    # Click Next
                    time.sleep(2)
                    next_buttons = driver.find_elements(By.TAG_NAME, "button")
                    for button in next_buttons:
                        if "Next" in button.text:
                            driver.execute_script("arguments[0].click();", button)
                            break
                    time.sleep(3)
    
    except Exception as e:
        logger.error(f"Error in process_storage_options: {e}")
    
    return trade_in_results

def main():
    args = parse_arguments()
    device_limit = args.num_devices
    debug_mode = args.debug
    
    driver = setup_driver(debug=debug_mode)
    all_results = []
    
    try:
        devices = get_device_list(driver, device_limit)
        logger.info(f"Found {len(devices)} devices")
        
        for device in devices:
            logger.info(f"Processing device: {device['name']}")
            
            if select_device(driver, device):
                device_results = process_storage_options(driver, device)
                if device_results:
                    all_results.extend(device_results)
                    logger.info(f"Collected {len(device_results)} results for {device['name']}")
                else:
                    logger.warning(f"No results for {device['name']}")
            else:
                logger.error(f"Failed to select device: {device['name']}")
        
        if all_results:
            logger.info(f"Total results: {len(all_results)}")
        else:
            logger.warning("No results collected")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        driver.quit()
        logger.info("Driver closed")

if __name__ == "__main__":
    main()