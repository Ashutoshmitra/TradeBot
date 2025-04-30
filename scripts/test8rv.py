#!/usr/bin/env python3
"""
test_iphone_15_plus.py - Test script to diagnose issues with SG_RV_Source8.py on iPhone 15 Plus page
Usage: python test_iphone_15_plus.py
Outputs results to output/test_iphone_15_plus.xlsx
"""

import argparse
import time
import os
import re
import sys
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import pandas as pd
import threading

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Detailed logging for debugging
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("test_iphone_15_plus.log")
    ]
)
logger = logging.getLogger("test_iphone_15_plus")

def setup_driver():
    """Setup an optimized Chrome webdriver."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument("--window-size=1280,720")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.images": 2,
        "profile.managed_default_content_settings.javascript": 1,
        "profile.default_content_setting_values.cookies": 1,
        "profile.managed_default_content_settings.plugins": 2,
        "disk-cache-size": 8192,
    })
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(10)
    driver.set_script_timeout(5)
    return driver

def safe_click(driver, element, retry=True, max_attempts=2):
    """Click element safely with retries."""
    for attempt in range(max_attempts):
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            element.click()
            logger.debug(f"Clicked element: {element.text or element.get_attribute('outerHTML')[:50]}")
            return True
        except:
            try:
                driver.execute_script("arguments[0].click();", element)
                logger.debug(f"Clicked element via JS: {element.text or element.get_attribute('outerHTML')[:50]}")
                return True
            except Exception as e:
                if attempt == max_attempts - 1:
                    logger.debug(f"Safe click failed after {max_attempts} attempts: {e}")
                    return False
                time.sleep(0.3)
    return False

def fast_find_elementalkanized(driver, by, value, timeout=1):
    """Find an element with a short timeout."""
    try:
        wait = WebDriverWait(driver, timeout)
        return wait.until(EC.presence_of_element_located((by, value)))
    except:
        return None

def fast_find_elements(driver, by, value, timeout=1):
    """Find elements with a short timeout."""
    try:
        wait = WebDriverWait(driver, timeout)
        return wait.until(EC.presence_of_all_elements_located((by, value)))
    except:
        return []

def threaded_page_timeout_handler(driver):
    """Handle page load timeout in a separate thread."""
    time.sleep(5)
    try:
        driver.execute_script("window.stop();")
    except:
        pass

def safe_get(driver, url, max_retries=2):
    """Navigate to URL with error handling."""
    logger.debug(f"Attempting to navigate to {url}")
    for attempt in range(max_retries):
        try:
            timeout_thread = threading.Thread(target=threaded_page_timeout_handler, args=(driver,))
            timeout_thread.daemon = True
            timeout_thread.start()
            driver.get(url)
            logger.debug(f"Successfully navigated to {url}")
            return True
        except TimeoutException:
            try:
                driver.execute_script("window.stop();")
                if url.split('/')[2] in driver.current_url:
                    logger.debug(f"Page partially loaded, continuing: {url}")
                    return True
            except:
                pass
            if attempt == max_retries - 1:
                logger.warning(f"Page load timeout after {max_retries} attempts: {url}")
            else:
                logger.debug(f"Page load timeout, attempt {attempt+1}/{max_retries}: {url}")
        except Exception as e:
            logger.warning(f"Navigation error: {str(e)[:100]}...")
        time.sleep(0.5)
    return False

def save_debug_screenshot(driver, model_name, storage, condition):
    """Save a screenshot for debugging."""
    try:
        debug_dir = "debug_screenshots"
        os.makedirs(debug_dir, exist_ok=True)
        safe_filename = f"{model_name}_{storage}_{condition}_{int(time.time())}".replace(" ", "_").replace("/", "_")
        screenshot_path = os.path.join(debug_dir, f"{safe_filename}.png")
        driver.save_screenshot(screenshot_path)
        logger.debug(f"Saved screenshot to {screenshot_path}")
    except Exception as e:
        logger.debug(f"Failed to save screenshot: {e}")

def save_debug_html(driver, model_name, storage, condition):
    """Save HTML content for debugging."""
    try:
        debug_dir = "debug_html"
        os.makedirs(debug_dir, exist_ok=True)
        safe_filename = f"{model_name}_{storage}_{condition}_{int(time.time())}".replace(" ", "_").replace("/", "_")
        html_path = os.path.join(debug_dir, f"{safe_filename}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.debug(f"Saved HTML to {html_path}")
    except Exception as e:
        logger.debug(f"Failed to save HTML: {e}")

def extract_price_from_text(text):
    """Extract price from text using regex patterns."""
    patterns = [
        r'S\$\s*(\d+)', r'\$\s*(\d+)', r'(\d+)\s*SELL', 
        r'vouchers!\s*\$(\d+)', r'offer!.*?(\d+)'
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            logger.debug(f"Extracted price with pattern {pattern}: {matches}")
            return f"S${matches[-1]}"
    logger.debug("No price patterns matched")
    return None

def process_device_condition(driver, model_name, storage_text, condition):
    """Process a specific device condition and extract trade-in value."""
    logger.info(f"Testing condition: {condition}")
    
    condition_selectors = [
        f"//p[contains(@class, 'reb-scr') and contains(text(), '{condition}')]",
        f"//div[contains(@id, 'eval-screen-condition')]//p[contains(text(), '{condition}')]",
        f"//div[contains(text(), 'screen')]//p[contains(text(), '{condition}')]",
        f"//p[contains(text(), '{condition}')]"
    ]
    
    screen_element = None
    for selector in condition_selectors:
        elements = fast_find_elements(driver, By.XPATH, selector)
        if elements:
            screen_element = elements[0]
            break
    
    if not screen_element:
        logger.warning(f"Could not find {condition} option")
        return None
    
    if not safe_click(driver, screen_element):
        logger.warning(f"Could not click on {condition} option")
        return None
    
    # Select "Flawless" for housing
    housing_selectors = [
        "//div[contains(@id, 'eval-housing-condition')]//p[contains(text(), 'Flawless')]",
        "//div[contains(text(), 'housing')]//p[contains(text(), 'Flawless')]"
    ]
    for selector in housing_selectors:
        housing_element = fast_find_element(driver, By.XPATH, selector, timeout=0.5)
        if housing_element:
            safe_click(driver, housing_element)
            break
    
    # Select Local Singapore Set
    local_set_element = fast_find_element(driver, By.XPATH, "//li[contains(text(), 'Local')]", timeout=0.5)
    if local_set_element:
        safe_click(driver, local_set_element)
    
    # Select "No" for warranty question
    warranty_selector = "//p[contains(text(), 'original warranty')]/ancestor::div[contains(@class, 'cus-yes-no')]/descendant::li[contains(text(), 'No')]"
    warranty_element = fast_find_element(driver, By.XPATH, warranty_selector, timeout=0.5)
    if warranty_element:
        logger.info("Selecting 'No' for warranty")
        safe_click(driver, warranty_element)
    
    # Select battery health (highest option)
    battery_selectors = [
        "//p[contains(text(), 'Battery Health')]/ancestor::div[contains(@class, 'cus-yes-no')]/descendant::li[contains(text(), '91%')]",
        "//ul[contains(@class, 'cus-battery-health')]/li[1]"
    ]
    for selector in battery_selectors:
        battery_element = fast_find_element(driver, By.XPATH, selector, timeout=0.5)
        if battery_element:
            logger.info(f"Selecting battery health: {battery_element.text}")
            safe_click(driver, battery_element)
            break
    
    # Click "Get Your Quote" button
    quote_button_selectors = [
        "//button[contains(text(), 'Get Your Quote')]",
        "//div[contains(@class, 'cus-btn-des')]//button",
        "//button[contains(@class, 'primary')]",
        "//button"
    ]
    
    quote_button = None
    for selector in quote_button_selectors:
        elements = fast_find_elements(driver, By.XPATH, selector, timeout=0.5)
        if elements:
            quote_button = elements[0]
            break
    
    if not quote_button:
        logger.warning("Could not find 'Get Your Quote' button")
        save_debug_screenshot(driver, model_name, storage_text, condition)
        save_debug_html(driver, model_name, storage_text, condition)
        return None
    
    # Check if button is disabled and handle required fields
    if quote_button.get_attribute("disabled"):
        logger.info("Quote button is disabled, checking required fields")
        required_fields = [
            ("Storage", ["//ul[contains(@class, 'reb-storage-list')]/li[contains(@class, 'reb-storage')]"], "reb-storage"),
            ("Battery Health", battery_selectors, "cus-battery-health"),
            ("Local/Export Set", ["//li[contains(text(), 'Local')]"], None)
        ]
        for field_name, selectors, class_name in required_fields:
            for selector in selectors:
                elements = fast_find_elements(driver, By.XPATH, selector, timeout=0.5)
                if elements:
                    for element in elements:
                        if class_name and class_name in element.get_attribute("class") and "reb-selected" in element.get_attribute("class"):
                            continue
                        logger.info(f"Selecting {field_name}: {element.text}")
                        if safe_click(driver, element):
                            time.sleep(0.2)
                            break
                    break
        
        # Re-check button state
        if quote_button.get_attribute("disabled"):
            logger.warning("Quote button still disabled after selecting fields")
            save_debug_screenshot(driver, model_name, storage_text, condition)
            save_debug_html(driver, model_name, storage_text, condition)
            return None
    
    if not safe_click(driver, quote_button):
        logger.warning("Failed to click quote button")
        save_debug_screenshot(driver, model_name, storage_text, condition)
        save_debug_html(driver, model_name, storage_text, condition)
        return None
    
    time.sleep(1)  # Wait for price to load
    
    page_text = driver.page_source
    price_value = extract_price_from_text(page_text)
    
    if price_value:
        logger.info(f"Found trade-in value: {price_value} for {model_name}, {storage_text}, {condition}")
        numeric_price = re.sub(r'[^0-9]', '', price_value)
        return {
            "model": model_name,
            "storage": storage_text,
            "condition": condition,
            "trade_in_value": price_value,
            "numeric_value": numeric_price
        }
    else:
        logger.warning(f"Could not find price for {model_name}, {storage_text}, {condition}")
        save_debug_screenshot(driver, model_name, storage_text, condition)
        save_debug_html(driver, model_name, storage_text, condition)
        return None

def test_iphone_15_plus(driver, output_file):
    """Test scraping for iPhone 15 Plus."""
    model_url = "https://reebelo.sg/buyback-form/iPhone-15-Plus?brand=apple&category=phone&condition=used"
    model_name = "iPhone 15 Plus"
    logger.info(f"Testing model: {model_name} at {model_url}")
    
    results = []
    
    # Navigate to model page
    if not safe_get(driver, model_url):
        logger.error(f"Failed to load model page: {model_url}")
        return results
    
    # Extract storage options
    storage_selectors = [
        "//ul[contains(@class, 'reb-storage-list')]/li[contains(@class, 'reb-storage')]",
        "//div[contains(text(), 'storage')]/following-sibling::div//li"
    ]
    
    storage_text = None
    for selector in storage_selectors:
        storage_elements = fast_find_elements(driver, By.XPATH, selector, timeout=1)
        if storage_elements:
            storage_element = storage_elements[0]  # Select first storage option
            storage_text = storage_element.text.strip()
            logger.info(f"Attempting to select storage: {storage_text}")
            if safe_click(driver, storage_element):
                time.sleep(0.2)
                selected_elements = fast_find_elements(driver, By.XPATH, f"{selector}[contains(@class, 'reb-selected')]")
                if any(storage_text in elem.text.strip() for elem in selected_elements):
                    logger.info(f"Successfully selected storage: {storage_text}")
                    break
                else:
                    logger.warning("Storage selection not confirmed")
                    storage_text = None
    if not storage_text:
        logger.error("Failed to select storage, using 'Default'")
        storage_text = "Default"
    
    # Process all conditions
    conditions = ["Flawless", "Minor Scratches", "Cracked or chipped"]
    for condition in conditions:
        # Process condition
        result = process_device_condition(driver, model_name, storage_text, condition)
        if result:
            trade_in = {
                "Country": "Singapore",
                "Device Type": "Smartphone",
                "Brand": "Apple",
                "Model": result.get("model", model_name),
                "Capacity": result.get("storage", storage_text),
                "Color": "N/A",
                "Launch RRP": "N/A",
                "Condition": result.get("condition", condition),
                "Value Type": "Trade-in",
                "Currency": "SGD",
                "Value": result.get("numeric_value", ""),
                "Source": "test_iphone_15_plus",
                "Updated on": time.strftime("%Y-%m-%d"),
                "Updated by": "",
                "Comments": "",
                "URL": model_url
            }
            results.append(trade_in)
            
            # Save to Excel immediately
            update_excel_file(trade_in, output_file)
        
        # Reload page for next condition
        if condition != conditions[-1]:
            logger.info(f"Reloading page for next condition: {conditions[conditions.index(condition)+1]}")
            if not safe_get(driver, model_url):
                logger.warning("Failed to reload page, skipping remaining conditions")
                break
            # Re-select storage
            if storage_text != "Default":
                for selector in storage_selectors:
                    elements = fast_find_elements(driver, By.XPATH, selector, timeout=1)
                    if elements:
                        for element in elements:
                            if element.text.strip() == storage_text:
                                logger.info(f"Re-selecting storage: {storage_text}")
                                safe_click(driver, element)
                                time.sleep(0.2)
                                break
                        break
    
    return results

def update_excel_file(new_data, output_file):
    """Update Excel file with new data."""
    try:
        if os.path.exists(output_file):
            try:
                existing_df = pd.read_excel(output_file)
                updated_df = pd.concat([existing_df, pd.DataFrame([new_data])], ignore_index=True)
            except Exception as e:
                logger.warning(f"Could not read existing Excel file: {e}")
                updated_df = pd.DataFrame([new_data])
        else:
            updated_df = pd.DataFrame([new_data])
        updated_df.to_excel(output_file, index=False)
        logger.debug(f"Updated Excel file: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to update Excel file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test scraper for iPhone 15 Plus on Reebelo")
    args = parser.parse_args()
    
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "test_iphone_15_plus.xlsx")
    
    logger.info(f"Results will be saved to: {output_file}")
    
    # Create empty Excel file if it doesn't exist
    if not os.path.exists(output_file):
        pd.DataFrame(columns=[
            "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
            "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
            "Source", "Updated on", "Updated by", "Comments", "URL"
        ]).to_excel(output_file, index=False)
        logger.info(f"Created new Excel file: {output_file}")
    
    driver = setup_driver()
    try:
        logger.info("="*50)
        logger.info("TESTING IPHONE 15 PLUS")
        logger.info("="*50)
        results = test_iphone_15_plus(driver, output_file)
        logger.info(f"Completed testing, found {len(results)} records")
        logger.info(f"Results saved to {output_file}")
    except Exception as e:
        logger.error(f"Error during testing: {e}")
    finally:
        driver.quit()
        logger.info("Test script completed")

if __name__ == "__main__":
    main()