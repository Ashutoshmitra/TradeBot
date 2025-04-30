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
from selenium.common.exceptions import NoSuchElementException
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
    "Microsoft": ["surface", "microsoft"],
}

def setup_driver():
    """Setup and return a Chrome webdriver with appropriate options."""
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Run in headless mode
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

def extract_device_info(driver, url):
    """Extract information from a device page."""
    print(f"Scraping data from {url}")
    driver.get(url)
    time.sleep(3)  # Wait for page to load
    
    try:
        # Extract device name and price
        device_name = driver.find_element(By.ID, "e2e-product-name").text
        print(f"Found device: {device_name}")
        
        # Extract price
        price_element = driver.find_element(By.ID, "e2e-product-price")
        price_text = price_element.text
        
        # First, remove all currency symbols and non-numeric characters except for numbers, commas, dots
        clean_price_text = re.sub(r'[^0-9,.]', '', price_text)
        
        # Then remove commas (e.g., "1,235" -> "1235")
        clean_price_text = clean_price_text.replace(',', '')
        
        # Try to extract the full numeric value
        if clean_price_text:
            price = clean_price_text
        else:
            # Fallback to regex methods
            price_value = re.search(r'SGD\s*([\d,.]+)', price_text)
            if not price_value:
                # Try alternate format like "$750.00"
                price_value = re.search(r'\$\s*([\d,.]+)', price_text)
            
            if price_value:
                price = price_value.group(1).replace(',', '')  # Remove commas
            else:
                price = ""
                
        print(f"Original price text: {price_text}, Extracted price: {price}")
        
        # Determine if it's a smartphone or tablet based on device name
        full_name = device_name.strip()
        if any(tablet_term in full_name.lower() for tablet_term in ["tab", "ipad", "pad", "tablet"]):
            device_type = "Tablet"
        else:
            device_type = "SmartPhone"
        
        # Identify the brand using our enhanced method
        brand = identify_brand(full_name)
        model = full_name
        
        # Extract capacity
        capacity = ""
        # Look for capacity in the storage section first
        try:
            storage_elements = driver.find_elements(By.CSS_SELECTOR, "#e2e-product-storage a")
            for element in storage_elements:
                if "border-gray-700" in element.get_attribute("class"):
                    capacity = element.text
                    print(f"Found capacity from storage section: {capacity}")
                    break
        except Exception as e:
            print(f"Error extracting capacity from storage section: {e}")
            
        # If not found in storage section, try to extract from name
        if not capacity:
            capacity_match = re.search(r'(\d+(?:\.\d+)?)\s*GB', device_name)
            if capacity_match:
                capacity = capacity_match.group(0)
        
        # Extract condition
        condition = "Excellent"  # Default value
        try:
            condition_elements = driver.find_elements(By.CSS_SELECTOR, "#e2e-product-condition a")
            for element in condition_elements:
                # Look for the active condition (highlighted with border)
                if "border-gray-700" in element.get_attribute("class"):
                    condition_text = element.text
                    # Look for the first meaningful text that could be a condition
                    condition_words = ["Premium", "Excellent", "Good", "Pristine", "Acceptable", "Very Good"]
                    
                    # Check the text for known condition words
                    for text in condition_text.split('\n'):
                        text = text.strip()
                        if text in condition_words:
                            condition = text
                            print(f"Found condition: {condition}")
                            break
                    
                    # If no clear condition was found, try to extract the first meaningful text
                    if condition == "Excellent":  # Still the default
                        for text in condition_text.split('\n'):
                            text = text.strip()
                            if text and text not in ['$', '.', '00', '0'] and not text.startswith('$'):
                                if len(text) > 1 and not text.replace('.', '').isdigit():
                                    condition = text
                                    print(f"Found condition: {condition}")
                                    break
        except Exception as e:
            print(f"Error extracting condition: {e}")
        
        # Current date for "Updated on"
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Debug output to verify extraction
        print(f"Extracted Brand: {brand}, Model: {model}, Capacity: {capacity}, Condition: {condition}, Price: {price}")
        
        return {
            "Country": "Singapore",
            "Device Type": device_type,
            "Brand": brand,
            "Model": model,
            "Capacity": capacity,
            "Color": "",  # Not scraping as per requirements
            "Launch RRP": "",  # Not scraping as per requirements
            "Condition": condition,
            "Value Type": "Sell-Off",
            "Currency": "SGD",
            "Value": price,
            "Source": "SG_SO_Source3",
            "Updated on": today,
            "Updated by": "",  # Not scraping as per requirements
            "Comments": ""  # Not scraping as per requirements
        }
    except Exception as e:
        print(f"Error extracting device info: {e}")
        return None

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

def update_excel_file(device_info):
    """Add a device to the Excel file."""
    if os.path.exists(OUTPUT_FILE):
        # Read existing data
        df = pd.read_excel(OUTPUT_FILE)
        
        # Add the new device
        df = pd.concat([df, pd.DataFrame([device_info])], ignore_index=True)
        
        # Save back to Excel
        df.to_excel(OUTPUT_FILE, index=False, sheet_name="Sheet")
        print(f"Updated {OUTPUT_FILE} with {device_info['Brand']} - {device_info['Model']} ({device_info['Capacity']})")
    else:
        # Create new file with the device
        df = pd.DataFrame([device_info])
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        
        # Save to Excel
        df.to_excel(OUTPUT_FILE, index=False, sheet_name="Sheet")
        print(f"Created {OUTPUT_FILE} with {device_info['Brand']} - {device_info['Model']} ({device_info['Capacity']})")

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
            device_info = extract_device_info(driver, url)
            if device_info:
                all_devices.append(device_info)
                update_excel_file(device_info)
        
        # Scrape tablets
        tablet_urls = get_device_urls(driver, TABLETS_URL, max_devices)
        for url in tablet_urls:
            device_info = extract_device_info(driver, url)
            if device_info:
                all_devices.append(device_info)
                update_excel_file(device_info)
        
        # Print summary
        print("\nScraping completed!")
        print(f"Total devices scraped: {len(all_devices)}")
        print(f"Smartphones: {sum(1 for d in all_devices if d['Device Type'] == 'SmartPhone')}")
        print(f"Tablets: {sum(1 for d in all_devices if d['Device Type'] == 'Tablet')}")
        print(f"Data saved to {OUTPUT_FILE}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()