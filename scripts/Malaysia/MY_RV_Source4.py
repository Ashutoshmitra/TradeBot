import argparse
import time
import logging
import os
import re
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Scrape uMobile trade-in values')
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

def extract_devices_data(driver):
    results = []
    
    try:
        # Load the main page
        driver.get("https://umobile-tradein.bolttech.my/my/TradeIn")
        time.sleep(5)  # Give time for the page to fully load
        
        # Find all suggestion items
        suggestion_items = driver.find_elements(By.CSS_SELECTOR, 
            "div.general-trade-in-carrier__suggestion-item[data-device-description][data-device-value]")
        
        logger.info(f"Found {len(suggestion_items)} device entries")
        
        device_count = 0
        for item in suggestion_items:
            try:
                full_name = item.get_attribute("data-device-description").strip()
                price_text = item.get_attribute("data-device-value").strip()
                
                # Skip entries without valid data
                if not full_name or not price_text:
                    continue
                
                logger.info(f"Processing: {full_name} - {price_text}")
                
                # Extract brand and model
                brand = "Unknown"
                name_lower = full_name.lower()
                
                if "apple" in name_lower or "iphone" in name_lower or "ipad" in name_lower:
                    brand = "Apple"
                elif "samsung" in name_lower:
                    brand = "Samsung"
                elif "xiaomi" in name_lower:
                    brand = "Xiaomi"
                elif "oppo" in name_lower:
                    brand = "OPPO"
                elif "google" in name_lower:
                    brand = "Google"
                elif "honor" in name_lower:
                    brand = "Honor"
                elif "nothing" in name_lower:
                    brand = "Nothing"
                elif "huawei" in name_lower:
                    brand = "Huawei"
                elif "sony" in name_lower:
                    brand = "Sony"
                elif "realme" in name_lower:
                    brand = "Realme"
                elif "vivo" in name_lower:
                    brand = "Vivo"
                elif "zte" in name_lower:
                    brand = "ZTE"
                
                # Determine device type
                device_type = "SmartPhone"
                if any(keyword in name_lower for keyword in ["ipad", "tab", "tablet"]):
                    device_type = "Tablet"
                elif any(keyword in name_lower for keyword in ["macbook", "laptop", "notebook"]):
                    device_type = "Laptop"
                elif any(keyword in name_lower for keyword in ["watch", "galaxy watch", "apple watch"]):
                    device_type = "SmartWatch"
                
                # Extract capacity if available
                capacity = ""
                capacity_match = re.search(r'(\d+\s*[GT]B)', full_name, re.IGNORECASE)
                if capacity_match:
                    capacity = capacity_match.group(1).upper()
                
                # Extract price value
                price_clean = re.sub(r'[^\d.]', '', price_text.split()[-1])
                
                # Create a record for the good condition (we only have one price)
                results.append({
                    'Country': 'Malaysia',
                    'Device Type': device_type,
                    'Brand': brand,
                    'Model': full_name,
                    'Capacity': capacity,
                    'Color': '',
                    'Launch RRP': '',
                    'Condition': 'Good',  # Assume the listed price is for good condition
                    'Value Type': 'Trade-in',
                    'Currency': 'MYR',
                    'Value': price_clean,
                    'Source': 'MY_RV_Source4',
                    'Updated on': datetime.now().strftime('%Y-%m-%d'),
                    'Updated by': '',
                    'Comments': ''
                })
                
                device_count += 1
                
            except Exception as e:
                logger.error(f"Error processing device: {e}")
        
        logger.info(f"Successfully processed {device_count} devices")
        
    except Exception as e:
        logger.error(f"Error extracting device data: {e}")
    
    return results

def save_results(results, filename='MY_RV_Source4.xlsx'):
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
        # Extract all device data at once since it's on a single page
        all_results = extract_devices_data(driver)
        
        # Apply device limit if specified
        if device_limit > 0 and len(all_results) > device_limit:
            all_results = all_results[:device_limit]
            logger.info(f"Limited to {device_limit} devices as requested")
        
        # Save the results
        if all_results:
            save_results(all_results)
            logger.info(f"Collected data for {len(all_results)} devices")
        else:
            logger.warning("No results found")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        driver.quit()
        logger.info("Driver closed")

if __name__ == "__main__":
    main()