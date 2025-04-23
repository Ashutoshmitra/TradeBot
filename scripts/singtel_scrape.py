import argparse
import json
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import urllib3
import os

def extract_trade_in_values(output_excel_path="singtel_tradein_values.xlsx", limit=None, headless=True):
    """
    Extracts trade-in values from Singtel website and saves to Excel
    
    Args:
        output_excel_path (str): Path to the output Excel file
        limit (int, optional): Limit the number of items per brand for testing
        headless (bool): Whether to run the browser in headless mode
        
    Returns:
        DataFrame: The data extracted, or None if extraction failed
    """
    # Increase timeout for urllib3
    urllib3.Timeout.DEFAULT_TIMEOUT = 30
    
    # Setup Chrome options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--window-size=1920,1080")
    # Optimize page loading
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.page_load_strategy = 'eager'  # Don't wait for all resources to load
    
    print("Initializing driver...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    # Set page load timeout
    driver.set_page_load_timeout(30)
    
    try:
        print("Opening website...")
        driver.get("https://www.singtel.com/personal/products-services/mobile#banner2")
        
        # Instead of fixed sleep, use WebDriverWait to wait for specific element
        print("Waiting for page to load...")
        wait = WebDriverWait(driver, 20)
        
        # First check if we can find the TradeInWidget container
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.lux-component-container[component="TradeInWidget"]')))
            print("TradeInWidget container found!")
        except Exception as e:
            print(f"TradeInWidget container not found: {e}")
            # Try to find any content to confirm page loaded
            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            print("At least body element loaded.")
        
        print("Extracting data model...")
        # Extract the data model from the HTML
        data_model_script = driver.execute_script(
            """
            const widgetContainer = document.querySelector('.lux-component-container[component="TradeInWidget"]');
            if (widgetContainer) {
                return widgetContainer.getAttribute('datamodel');
            }
            return null;
            """
        )
        
        # If direct extraction failed, try to find the widget data in page source
        if not data_model_script:
            print("Direct extraction failed, searching in page source...")
            page_source = driver.page_source
            import re
            # Look for JSON data in the page source that might contain the trade-in data
            pattern = r'datamodel="([^"]*)"'
            matches = re.findall(pattern, page_source)
            if matches:
                data_model_script = matches[0].replace('&quot;', '"')
                print("Found data model in page source")
            else:
                print("Could not find data model in page source")
    except Exception as e:
        print(f"Error during website navigation: {e}")
        driver.save_screenshot("error_screenshot.png")
        print("Screenshot saved as error_screenshot.png")
        driver.quit()
        return
    finally:
        driver.quit()
    
    if not data_model_script:
        print("Failed to extract data model")
        return
    
    # Try to parse the data model
    try:
        # Clean up the extracted data if needed
        data_model_script = data_model_script.replace('&quot;', '"')
        data_model = json.loads(data_model_script)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON data: {e}")
        print(f"First 200 characters of data: {data_model_script[:200]}")
        return
    
    results = []
    brands_to_extract = ["Apple", "Google"]
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        for brand in data_model["brands"]:
            if brand["title"] not in brands_to_extract:
                continue
                
            brand_name = brand["title"]
            print(f"Processing brand: {brand_name}")
            
            count = 0
            for model in brand["models"]:
                model_name = model["title"]
                
                # Skip "For Recycling"
                if model_name == "For Recycling":
                    continue
                    
                for size in model["sizes"]:
                    size_name = size["title"]
                    trade_price = size["tradePrice"]
                    
                    # Some entries don't have sizes (empty string)
                    if size_name == "":
                        size_name = "N/A"
                    
                    # Determine device type based on model name
                    device_type = "Phone"
                    if any(tablet_term in model_name.lower() for tablet_term in ["tab", "ipad", "pad", "tablet"]):
                        device_type = "Tablet"
                    
                    # Format the trade price correctly (just the numeric value)
                    trade_price_value = str(trade_price)
                    
                    # Create a row with the standardized columns
                    results.append({
                        "Country": "Singapore",
                        "Device Type": device_type,
                        "Brand": brand_name,
                        "Model": model_name,
                        "Capacity": size_name,
                        "Color": "",  # Left blank as requested
                        "Launch RRP": "",  # Left blank as requested
                        "Condition": "Flawless",  # Default to "Flawless" for Singtel
                        "Value Type": "Trade-in",
                        "Currency": "SGD",
                        "Value": trade_price_value,
                        "Source": "SG_RV_Source4",
                        "Updated on": current_date,
                        "Updated by": "",  # Left blank as requested
                        "Comments": ""  # Left blank as requested
                    })
                    
                    count += 1
                    if limit and count >= limit:
                        break
                        
                if limit and count >= limit:
                    break
    except Exception as e:
        print(f"Error processing data model: {e}")
        if not results:
            return
    
    # Define the column order
    columns = [
        "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
        "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
        "Source", "Updated on", "Updated by", "Comments"
    ]
    
    # Create DataFrame and save to Excel
    df = pd.DataFrame(results)
    
    # Ensure columns are in the right order
    df = df[columns]
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
    
    # Save to Excel
    df.to_excel(output_excel_path, index=False)
    
    print(f"Extracted {len(results)} trade-in values")
    print(f"Results saved to {output_excel_path}")
    
    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape trade-in values from Singtel website")
    parser.add_argument("-n", "--limit", type=int, help="Limit the number of items to extract per brand (for testing)")
    parser.add_argument("-o", "--output", type=str, help="Output Excel file path", default="singtel_tradein_values.xlsx")
    parser.add_argument("--no-headless", action="store_true", help="Run without headless mode (shows browser)")
    args = parser.parse_args()
    
    # Ensure output path is properly set
    output_path = args.output
    
    extract_trade_in_values(output_path, args.limit, headless=not args.no_headless)