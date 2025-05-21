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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Scrape Carousell trade-in price ranges')
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
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def get_device_list(driver, limit=None):
    driver.get("https://sellto.carousell.sg/")
    time.sleep(3)
    
    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[id^='react-select-'][type='text']"))
        )
        
        search_box.send_keys(" ")
        time.sleep(2)
        
        device_options = driver.find_elements(By.XPATH, "//div[contains(@id, 'react-select-') and contains(@class, 'option')]")
        if not device_options:
            logger.error("No device options found")
            return []
        
        logger.info(f"Found {len(device_options)} device options")
        
        devices = []
        for option in device_options:
            device_name = option.text.strip()
            
            if device_name:
                # Enhanced device type detection
                device_name_lower = device_name.lower()
                
                # Determine device type based on keywords
                if any(keyword in device_name_lower for keyword in ["ipad", "tab", "tablet"]):
                    device_type = "Tablet"
                elif any(keyword in device_name_lower for keyword in ["macbook", "laptop", "notebook", "imac", "mac mini", "mac pro"]):
                    device_type = "Laptop"
                elif any(keyword in device_name_lower for keyword in ["watch", "galaxy watch", "apple watch"]):
                    device_type = "SmartWatch"
                elif any(keyword in device_name_lower for keyword in ["airpod", "earpod", "earphone", "headphone", "buds"]):
                    device_type = "Airpods"
                elif any(keyword in device_name_lower for keyword in ["tv", "television"]):
                    device_type = "TV"
                else:
                    # Default to Smartphone for other devices
                    device_type = "SmartPhone"
                
                # Determine brand
                brand = "Unknown"
                if "apple" in device_name_lower or any(keyword in device_name_lower for keyword in ["iphone", "ipad", "macbook", "airpod", "apple watch"]):
                    brand = "Apple"
                elif "samsung" in device_name_lower:
                    brand = "Samsung"
                elif "xiaomi" in device_name_lower:
                    brand = "Xiaomi"
                elif "oppo" in device_name_lower:
                    brand = "OPPO"
                elif "google" in device_name_lower:
                    brand = "Google"
                elif "honor" in device_name_lower:
                    brand = "Honor"
                elif "nothing" in device_name_lower:
                    brand = "Nothing"
                elif "huawei" in device_name_lower:
                    brand = "Huawei"
                elif "sony" in device_name_lower:
                    brand = "Sony"
                
                logger.info(f"Found device: {device_name} (Type: {device_type}, Brand: {brand})")
                devices.append({
                    'name': device_name,
                    'type': device_type,
                    'brand': brand
                })
        
        if limit and len(devices) > limit:
            devices = devices[:limit]
        
        return devices
    
    except Exception as e:
        logger.error(f"Error getting device list: {e}")
        return []

def select_device(driver, device):
    driver.get("https://sellto.carousell.sg/")
    time.sleep(3)
    
    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[id^='react-select-'][type='text']"))
        )
        
        search_box.clear()
        search_box.send_keys(device['name'])
        time.sleep(2)
        
        options = driver.find_elements(By.XPATH, "//div[contains(@class, 'option')]")
        for option in options:
            if device['name'].lower() in option.text.lower():
                option.click()
                logger.info(f"Selected device: {device['name']}")
                time.sleep(3)
                return True
        
        search_box.send_keys(Keys.ENTER)
        logger.info(f"Selected device using Enter key: {device['name']}")
        time.sleep(3)
        return True
        
    except Exception as e:
        logger.error(f"Error selecting device: {e}")
        return False

def extract_price_table(driver, device):
    results = []
    
    try:
        # Check for storage options
        storage_options = driver.find_elements(By.CSS_SELECTOR, 
            "div.py-\\[0\\.5rem\\].px-3.md\\:px-5.bg-white.rounded-xl.border.flex.cursor-pointer, div.rounded-xl.border.flex.cursor-pointer")
        
        if storage_options:
            # Click Next button
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                if button.is_displayed() and button.is_enabled():
                    driver.execute_script("arguments[0].click();", button)
                    break
        
        time.sleep(3)
        
        # Find section with price table
        sections = driver.find_elements(By.TAG_NAME, "section")
        for section in sections:
            h3_elements = section.find_elements(By.TAG_NAME, "h3")
            if h3_elements and "Estimated Price" in h3_elements[0].text:
                
                rows = section.find_elements(By.CSS_SELECTOR, "tbody tr")
                if not rows:
                    continue
                
                # Track storage+connectivity combinations to avoid duplicates
                # Dictionary to store price ranges for each storage+connectivity combination
                storage_prices = {}
                
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 2:
                            full_storage_text = cells[0].text.strip()
                            price_range_text = cells[1].text.strip()
                            
                            # Extract just the capacity part (e.g., "64GB")
                            storage_match = re.search(r'(\d+\s*[GT]B)', full_storage_text, re.IGNORECASE)
                            if storage_match:
                                storage_text = storage_match.group(1).upper()
                            else:
                                storage_text = "Unknown"
                            
                            # Extract connectivity (WiFi-Only or LTE)
                            connectivity = "Wifi-Only"
                            if "LTE" in full_storage_text:
                                connectivity = "LTE"
                            
                            # Create a unique storage+connectivity key
                            storage_conn_key = f"{storage_text}-{connectivity}"
                            
                            # Extract min and max prices
                            price_match = re.search(r'S\$\s*([\d,]+)\s*-\s*S\$\s*([\d,]+)', price_range_text)
                            if price_match:
                                min_price = price_match.group(1).replace(',', '')
                                max_price = price_match.group(2).replace(',', '')
                                
                                # Store the prices for this storage+connectivity combination
                                # Only if not already stored
                                if storage_conn_key not in storage_prices:
                                    storage_prices[storage_conn_key] = {
                                        'storage': storage_text,
                                        'connectivity': connectivity,
                                        'min_price': min_price,
                                        'max_price': max_price
                                    }
                    except Exception as e:
                        logger.error(f"Error processing row: {e}")
                
                # Now process each unique storage+connectivity combination
                for key, price_data in storage_prices.items():
                    logger.info(f"Extracted: {device['name']} {price_data['storage']} {price_data['connectivity']} - " +
                               f"Price range: {price_data['min_price']} to {price_data['max_price']}")
                    
                    # Add record for low price (Damaged condition)
                    results.append({
                        'Country': 'Singapore',
                        'Device Type': device['type'],
                        'Brand': device['brand'],
                        'Model': f"{device['name']} {price_data['storage']} {price_data['connectivity']}",
                        'Capacity': price_data['storage'],
                        'Color': '',
                        'Launch RRP': '',
                        'Condition': 'Damaged',
                        'Value Type': 'Trade-in',
                        'Currency': 'SGD',
                        'Value': price_data['min_price'],
                        'Source': 'SG_RV_Source6',
                        'Updated on': datetime.now().strftime('%Y-%m-%d'),
                        'Updated by': '',
                        'Comments': ''
                    })
                    
                    # Add record for high price (Good condition)
                    results.append({
                        'Country': 'Singapore',
                        'Device Type': device['type'],
                        'Brand': device['brand'],
                        'Model': f"{device['name']} {price_data['storage']} {price_data['connectivity']}",
                        'Capacity': price_data['storage'],
                        'Color': '',
                        'Launch RRP': '',
                        'Condition': 'Good',
                        'Value Type': 'Trade-in',
                        'Currency': 'SGD',
                        'Value': price_data['max_price'],
                        'Source': 'SG_RV_Source6',
                        'Updated on': datetime.now().strftime('%Y-%m-%d'),
                        'Updated by': '',
                        'Comments': ''
                    })
                
                break  # Found the table, no need to check other sections
    
    except Exception as e:
        logger.error(f"Error extracting price table: {e}")
    
    return results

def save_results(results, filename='SG_RV_Source6.xlsx'):
    if not results:
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

def main():
    args = parse_arguments()
    device_limit = args.num_devices
    debug_mode = args.debug
    
    driver = setup_driver(debug=debug_mode)
    
    try:
        devices = get_device_list(driver, device_limit)
        logger.info(f"Found {len(devices)} devices")
        
        for device in devices:
            logger.info(f"Processing device: {device['name']}")
            
            if select_device(driver, device):
                device_results = extract_price_table(driver, device)
                if device_results:
                    save_results(device_results)
                    logger.info(f"Collected {len(device_results)} results for {device['name']}")
                else:
                    logger.warning(f"No results for {device['name']}")
            
            time.sleep(2)  # Pause between devices
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        driver.quit()
        logger.info("Driver closed")

if __name__ == "__main__":
    main()