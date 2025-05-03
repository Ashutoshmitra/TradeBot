#!/usr/bin/env python3
import argparse
import datetime
import os
import pandas as pd
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# Define URLs
SMARTPHONES_URL = "https://reebelo.sg/collections/smartphones?sort=latest-release"
TABLETS_URL = "https://reebelo.sg/collections/tablets?sort=latest-release"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "SG_SO_Source3.xlsx")

# Define brand detection patterns
BRAND_PATTERNS = {
    "Apple": ["iphone", "ipad", "macbook", "airpods", "apple watch", "apple"],
    "Samsung": ["galaxy", "samsung", "note", "fold", "flip", "tab s", "tab a"],
    "Google": ["pixel", "google"],
    "Huawei": ["huawei", "mate", "p30", "p40", "p50", "nova"],
    "Xiaomi": ["xiaomi", "redmi", "poco", "mi pad"],
    "Oppo": ["oppo", "find n", "find x", "reno"],
    "OnePlus": ["oneplus", "one plus"],
    "Sony": ["sony", "xperia"],
    "LG": ["lg ", "lg v", "lg g"],
    "Motorola": ["motorola", "moto g", "moto e", "razr"],
    "Vivo": ["vivo"],
    "Realme": ["realme"],
    "Honor": ["honor"],
    "Nothing": ["nothing phone"],
    "Nokia": ["nokia"],
    "Asus": ["asus", "rog phone", "zenfone"],
    "Lenovo": ["lenovo", "tab m", "tab p"],
    "HTC": ["htc", "one m", "desire", "u ultra", "u11", "u12"],
    "Microsoft": ["surface", "microsoft"],
}

def setup_driver():
    """Setup and return a Chrome webdriver with appropriate options."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def get_device_urls(driver, base_url, max_devices=None):
    """Get URLs for devices from the collection page."""
    driver.get(base_url)
    print(f"Scraping device URLs from {base_url}")
    time.sleep(3)  # Wait for page to load
    
    # Find all device cards
    device_cards = driver.find_elements(By.CSS_SELECTOR, "div.flex.flex-col.border a")
    
    # Extract URLs
    urls = []
    for card in device_cards:
        try:
            url = card.get_attribute("href")
            if url and "/collections/" in url:
                urls.append(url)
                
                # Debug print to see what we're getting
                try:
                    device_name = card.find_element(By.CSS_SELECTOR, "h4").text
                    print(f"Found device: {device_name} - {url}")
                except:
                    print(f"Found device URL: {url}")
                
                if max_devices and len(urls) >= max_devices:
                    break
        except Exception as e:
            print(f"Error extracting URL: {e}")
    
    print(f"Found {len(urls)} device URLs")
    return urls

def identify_brand(device_name):
    """Identify the brand based on device name using pattern matching."""
    device_name_lower = device_name.lower()
    
    # First check for exact brand mentions at the start of the name
    for brand, patterns in BRAND_PATTERNS.items():
        if device_name_lower.startswith(brand.lower()):
            return brand
    
    # Then check for keywords that strongly indicate a specific brand
    for brand, patterns in BRAND_PATTERNS.items():
        for pattern in patterns:
            if pattern in device_name_lower:
                return brand
    
    # Special case handling for series that uniquely identify brands
    if re.search(r'\biphone\b|\bipad\b|\bwatch\b', device_name_lower):
        return "Apple"
    elif re.search(r'\bgalaxy\b|\bs\d+\b|\ba\d+\b|\bnote\b|\btab s\b|\btab a\b|\bfold\b|\bflip\b', device_name_lower):
        return "Samsung"
    
    # If no brand identified, return Unknown
    return "Unknown"

def extract_price_from_condition_element(condition_element):
    """Extract the price from a condition element."""
    try:
        # Look for the price in the element
        price_text = condition_element.text
        
        # Extract the price using regex
        price_match = re.search(r'\$([\d,]+(?:\.\d+)?)', price_text)
        if price_match:
            price = price_match.group(1).replace(',', '')
            return price
        
        # If regex fails, try to find the div with the price
        price_div = condition_element.find_element(By.CSS_SELECTOR, "div.mt-1")
        if price_div:
            price_text = price_div.text
            clean_price_text = re.sub(r'[^0-9,.]', '', price_text)
            price = clean_price_text.replace(',', '')
            return price
    except Exception as e:
        print(f"Error extracting price from condition element: {e}")
    
    return ""

def get_storage_options(driver):
    """Get all available storage options from the page."""
    try:
        storage_elements = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#e2e-product-storage a"))
        )
        return storage_elements
    except TimeoutException:
        print("Timed out waiting for storage elements")
        return []
    except Exception as e:
        print(f"Error getting storage options: {e}")
        return []

def get_condition_options(driver):
    """Get all available condition options from the page."""
    try:
        condition_elements = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[id^='e2e-product-condition-']"))
        )
        return condition_elements
    except TimeoutException:
        print("Timed out waiting for condition elements")
        return []
    except Exception as e:
        print(f"Error getting condition options: {e}")
        return []

def extract_device_info(driver, url):
    """Extract information from a device page including all storage and condition options."""
    print(f"Scraping data from {url}")
    driver.get(url)
    time.sleep(3)  # Wait for page to load
    
    all_device_infos = []  # Store all combinations
    
    try:
        # Extract device name
        device_name = driver.find_element(By.ID, "e2e-product-name").text
        print(f"Found device: {device_name}")
        
        # Determine if it's a smartphone or tablet based on device name
        full_name = device_name.strip()
        if any(tablet_term in full_name.lower() for tablet_term in ["tab", "ipad", "pad", "tablet"]):
            device_type = "Tablet"
        else:
            device_type = "SmartPhone"
        
        # Identify the brand using our enhanced method
        brand = identify_brand(full_name)
        model = full_name
        
        # Current date for "Updated on"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Get all storage options
        storage_options = get_storage_options(driver)
        
        # If no storage options found, create a single entry with the default view
        if not storage_options:
            # Get the currently selected condition
            try:
                condition_elements = get_condition_options(driver)
                if condition_elements:
                    for condition_element in condition_elements:
                        condition_text = condition_element.text.split('\n')[0].strip()
                        price = extract_price_from_condition_element(condition_element)
                        
                        capacity = ""
                        capacity_match = re.search(r'(\d+(?:\.\d+)?)\s*GB', device_name)
                        if capacity_match:
                            capacity = capacity_match.group(0)
                        
                        device_info = {
                            "Country": "Singapore",
                            "Device Type": device_type,
                            "Brand": brand,
                            "Model": model,
                            "Capacity": capacity,
                            "Color": "",  # Not scraping as per requirements
                            "Launch RRP": "",  # Not scraping as per requirements
                            "Condition": condition_text,
                            "Value Type": "Sell-Off",
                            "Currency": "SGD",
                            "Value": price,
                            "Source": "SG_SO_Source3",
                            "Updated on": today,
                            "Updated by": "",  # Not scraping as per requirements
                            "Comments": ""  # Not scraping as per requirements
                        }
                        all_device_infos.append(device_info)
                        print(f"Added entry with condition {condition_text} and price {price}")
            except Exception as e:
                print(f"Error getting condition info in default view: {e}")
                # Create a basic entry with whatever we've got
                device_info = {
                    "Country": "Singapore",
                    "Device Type": device_type,
                    "Brand": brand,
                    "Model": model,
                    "Capacity": "",
                    "Color": "",
                    "Launch RRP": "",
                    "Condition": "Unknown",
                    "Value Type": "Sell-Off",
                    "Currency": "SGD",
                    "Value": "",
                    "Source": "SG_SO_Source3",
                    "Updated on": today,
                    "Updated by": "",
                    "Comments": ""
                }
                all_device_infos.append(device_info)
        else:
            # Iterate through all storage options
            for storage_element in storage_options:
                try:
                    storage_value = storage_element.text.strip()
                    print(f"Clicking on storage option: {storage_value}")
                    
                    # Click on the storage option
                    driver.execute_script("arguments[0].click();", storage_element)
                    time.sleep(2)  # Wait for page to update
                    
                    # Get all condition options for this storage
                    condition_elements = get_condition_options(driver)
                    
                    for condition_element in condition_elements:
                        try:
                            # Extract condition name (first line of the text)
                            condition_text = condition_element.text.split('\n')[0].strip()
                            
                            # Extract price
                            price = extract_price_from_condition_element(condition_element)
                            
                            # Create a device info entry for this combination
                            device_info = {
                                "Country": "Singapore",
                                "Device Type": device_type,
                                "Brand": brand,
                                "Model": model,
                                "Capacity": storage_value,
                                "Color": "",  # Not scraping as per requirements
                                "Launch RRP": "",  # Not scraping as per requirements
                                "Condition": condition_text,
                                "Value Type": "Sell-Off",
                                "Currency": "SGD",
                                "Value": price,
                                "Source": "SG_SO_Source3",
                                "Updated on": today,
                                "Updated by": "",  # Not scraping as per requirements
                                "Comments": ""  # Not scraping as per requirements
                            }
                            
                            all_device_infos.append(device_info)
                            print(f"Added entry with storage {storage_value}, condition {condition_text}, and price {price}")
                        except Exception as e:
                            print(f"Error processing condition element: {e}")
                except Exception as e:
                    print(f"Error processing storage option {storage_element.text}: {e}")
        
        return all_device_infos
    except Exception as e:
        print(f"Error extracting device info: {e}")
        return []

def initialize_excel_file():
    """Create initial Excel file with column headers."""
    columns = [
        "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
        "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
        "Source", "Updated on", "Updated by", "Comments"
    ]
    
    # Create an empty DataFrame with the columns
    df = pd.DataFrame(columns=columns)
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # Save to Excel
    df.to_excel(OUTPUT_FILE, index=False, sheet_name="Sheet")
    print(f"Initialized output file at {OUTPUT_FILE}")
    
    return df

def update_excel_file(device_infos):
    """Add multiple devices to the Excel file."""
    if not device_infos:
        print("No device info to update")
        return
    
    if os.path.exists(OUTPUT_FILE):
        # Read existing data
        df = pd.read_excel(OUTPUT_FILE)
        
        # Add the new devices
        new_df = pd.DataFrame(device_infos)
        df = pd.concat([df, new_df], ignore_index=True)
        
        # Save back to Excel
        df.to_excel(OUTPUT_FILE, index=False, sheet_name="Sheet")
        print(f"Updated {OUTPUT_FILE} with {len(device_infos)} entries")
    else:
        # Create new file with the devices
        df = pd.DataFrame(device_infos)
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        
        # Save to Excel
        df.to_excel(OUTPUT_FILE, index=False, sheet_name="Sheet")
        print(f"Created {OUTPUT_FILE} with {len(device_infos)} entries")

def main():
    parser = argparse.ArgumentParser(description='Scrape device prices from reebelo.sg')
    parser.add_argument('-n', '--number', type=int, help='Number of devices to scrape per category (smartphones/tablets)')
    args = parser.parse_args()
    
    max_devices = args.number if args.number else None
    
    driver = setup_driver()
    
    # Initialize output file
    initialize_excel_file()
    all_devices = []
    
    try:
        # Scrape smartphones
        smartphone_urls = get_device_urls(driver, SMARTPHONES_URL, max_devices)
        for url in smartphone_urls:
            device_infos = extract_device_info(driver, url)
            if device_infos:
                all_devices.extend(device_infos)
                update_excel_file(device_infos)
        
        # Scrape tablets
        tablet_urls = get_device_urls(driver, TABLETS_URL, max_devices)
        for url in tablet_urls:
            device_infos = extract_device_info(driver, url)
            if device_infos:
                all_devices.extend(device_infos)
                update_excel_file(device_infos)
        
        # Print summary
        print("\nScraping completed!")
        print(f"Total combinations scraped: {len(all_devices)}")
        print(f"Smartphones: {sum(1 for d in all_devices if d['Device Type'] == 'SmartPhone')}")
        print(f"Tablets: {sum(1 for d in all_devices if d['Device Type'] == 'Tablet')}")
        print(f"Data saved to {OUTPUT_FILE}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()