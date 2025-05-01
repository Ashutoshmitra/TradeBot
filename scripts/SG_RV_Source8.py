#!/usr/bin/env python3
"""
SHOULD BE RUN IN HEAD MODE: UDPATED 1st MAY 2025
SG_RV_Source8.py - Efficient script to scrape trade-in values of smartphones and tablets from Reebelo
Usage: 
  python SG_RV_Source8.py (scrapes all smartphones and tablets)
  python SG_RV_Source8.py -n 3 (scrapes 3 smartphones and 3 tablets)
  python SG_RV_Source8.py -o output/SG_RV_Source8.xlsx (saves to specified file)
"""

import argparse
import time
import os
import sys
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import pandas as pd
import logging
import threading

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("reebelo_scraper")

def setup_driver():
    """Setup an optimized Chrome webdriver."""
    chrome_options = Options()
    # Performance optimizations
    # chrome_options.add_argument('--headless')
    chrome_options.add_argument("--window-size=1280,720")  # Smaller window = less data to render
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    
    # Optimize resource loading
    chrome_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.images": 2,  # Block images - major speed boost
        "profile.managed_default_content_settings.javascript": 1,  # Allow JS
        "profile.default_content_setting_values.cookies": 1,  # Allow cookies
        "profile.managed_default_content_settings.plugins": 2,  # Block plugins
        "disk-cache-size": 8192,  # Increase cache size
    })
    
    # Standard user agent
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Set very short timeouts to prevent long waits
    driver.set_page_load_timeout(10)
    driver.set_script_timeout(5)
    
    return driver

def safe_click(driver, element, retry=True):
    """Click element safely using JavaScript (more reliable than regular click)."""
    try:
        # First try regular click (faster)
        try:
            element.click()
            return True
        except:
            # Fallback to JS click
            driver.execute_script("arguments[0].click();", element)
            return True
    except Exception as e:
        if retry:
            try:
                # Try scrolling to element first then retry
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.1)  # Very short pause
                return safe_click(driver, element, retry=False)
            except:
                pass
        logger.debug(f"Safe click failed: {e}")
        return False

def fast_find_element(driver, by, value, timeout=1):
    """Find an element with a very short timeout."""
    try:
        wait = WebDriverWait(driver, timeout)
        return wait.until(EC.presence_of_element_located((by, value)))
    except:
        return None

def fast_find_elements(driver, by, value, timeout=1):
    """Find elements with a very short timeout."""
    try:
        wait = WebDriverWait(driver, timeout)
        return wait.until(EC.presence_of_all_elements_located((by, value)))
    except:
        return []

def threaded_page_timeout_handler(driver):
    """Run in a separate thread to ensure the browser continues after timeout."""
    time.sleep(5)  # Wait for max timeout
    try:
        # Force stop page loading if it's still loading
        driver.execute_script("window.stop();")
    except:
        pass

def safe_get(driver, url, max_retries=2):
    """Navigate to URL with smart error handling and forced continuation."""
    logger.debug(f"DEBUG: Attempting to navigate to {url}")
    for attempt in range(max_retries):
        try:
            # Start a timeout handler thread
            timeout_thread = threading.Thread(target=threaded_page_timeout_handler, args=(driver,))
            timeout_thread.daemon = True
            timeout_thread.start()
            
            # Try to navigate
            driver.get(url)
            logger.debug(f"DEBUG: Successfully navigated to {url}")
            return True
        except TimeoutException:
            # Page load timeout occurred, but we might have partial content
            try:
                # Force stop loading
                driver.execute_script("window.stop();")
                
                # If we've loaded enough of the page to work with, consider it a success
                if url.split('/')[2] in driver.current_url:
                    logger.debug(f"DEBUG: Page partially loaded, continuing: {url}")
                    return True
            except:
                pass
            
            # Log the timeout but don't show full stack trace
            if attempt == max_retries - 1:
                logger.warning(f"Page load timeout after {max_retries} attempts: {url}")
                logger.debug(f"DEBUG: Current URL after timeout: {driver.current_url}")
            else:
                logger.debug(f"DEBUG: Page load timeout, attempt {attempt+1}/{max_retries}: {url}")
        except Exception as e:
            logger.warning(f"Navigation error: {str(e)[:100]}...")
            logger.debug(f"DEBUG: Full navigation error: {str(e)}")
            
        # Short pause between retries
        time.sleep(0.5)
    
    return False

def save_debug_screenshot(driver, model_name, storage, condition):
    """Save a screenshot for debugging purposes"""
    try:
        debug_dir = "debug_screenshots"
        os.makedirs(debug_dir, exist_ok=True)
        safe_filename = f"{model_name}_{storage}_{condition}".replace(" ", "_").replace("/", "_")
        screenshot_path = os.path.join(debug_dir, f"{safe_filename}.png")
        driver.save_screenshot(screenshot_path)
        logger.debug(f"DEBUG: Saved screenshot to {screenshot_path}")
    except Exception as e:
        logger.debug(f"DEBUG: Failed to save screenshot: {e}")

def navigate_to_device_category(driver, device_type):
    """Navigate to device category with minimal waiting."""
    logger.info(f"Navigating to {device_type} category...")
    
    # Try direct navigation first (faster)
    if device_type.lower() == "smartphone":
        direct_url = "https://reebelo.sg/buyback/sell-phone"
    else:
        direct_url = "https://reebelo.sg/buyback/sell-tablet"
    
    if safe_get(driver, direct_url):
        if device_type.lower() in driver.current_url.lower():
            logger.info(f"Successfully navigated directly to {device_type} page")
            return True
    
    # Fallback to main page navigation
    safe_get(driver, "https://reebelo.sg/buyback/sell-electronic")
    
    # Find and click device category link
    if device_type.lower() == "smartphone":
        selector = "//a[contains(@href, '/buyback/sell-phone')]"
    else:
        selector = "//a[contains(@href, '/buyback/sell-tablet')]"
    
    element = fast_find_element(driver, By.XPATH, selector)
    if element and safe_click(driver, element):
        logger.info(f"Clicked on {device_type} category")
        return True
    else:
        logger.error(f"Could not navigate to {device_type} category")
        return False

def navigate_to_brand_page(driver, device_type, brand):
    """Navigate to a specific brand's page with minimal waiting."""
    if not navigate_to_device_category(driver, device_type):
        return False
    
    # Try to find and click on the brand link
    brand_xpath = f"//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{brand.lower()}')]"
    brand_element = fast_find_element(driver, By.XPATH, brand_xpath)
    
    if brand_element and safe_click(driver, brand_element):
        logger.info(f"Clicked on {brand} brand")
        return True
    
    # Fallback: try direct URL navigation
    fallback_url = f"https://reebelo.sg/buyback/sell-{brand.lower()}-{device_type.lower()}"
    logger.info(f"Direct navigation to {fallback_url}")
    safe_get(driver, fallback_url)
    
    # Check if we're on a page that seems to have the brand
    if brand.lower() in driver.current_url.lower() or brand.lower() in driver.page_source.lower():
        logger.info(f"Successfully navigated to {brand} page")
        return True
    else:
        logger.warning(f"Could not navigate to {brand} page")
        return False

def extract_price_from_text(text):
    """Extract price from text using regex patterns, prioritizing the main price display."""
    logger.debug(f"DEBUG: Starting price extraction from text")
    
    # First, try to find price in the best offer card section - this is most reliable
    best_offer_patterns = [
        r'vendor-content-price[^>]*vendor-content-price-selected[^>]*><h4>\$(\d+)</h4>',
        r'best-offer-card[^>]*>.*?vendor-content-price[^>]*><h4>\$(\d+)</h4>',
        r'best-offer.*?vendor-content-price.*?<h4>\$(\d+)</h4>'
    ]
    
    # Try the best offer patterns first
    for pattern in best_offer_patterns:
        logger.debug(f"DEBUG: Trying best offer pattern: {pattern}")
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            logger.debug(f"DEBUG: Best offer pattern {pattern} found matches: {matches}")
            return f"S${matches[0]}"
    
    # Fall back to simpler patterns if best offer not found
    fallback_patterns = [
        r'<h4>\$(\d+)</h4>',                # Price in h4 tag
        r'vendor-content-price.*?(\d+)',    # Price near vendor-content-price
        r'S\$\s*(\d+)',                     # S$ followed by digits
        r'\$\s*(\d+)',                      # $ followed by digits
        r'(\d+)\s*SELL',                    # Digits followed by SELL
        r'vouchers!\s*\$(\d+)',             # Price after "vouchers!"
        r'offer!.*?(\d+)'                   # Digits after "offer!"
    ]
    
    for pattern in fallback_patterns:
        logger.debug(f"DEBUG: Trying fallback pattern: {pattern}")
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            logger.debug(f"DEBUG: Fallback pattern {pattern} found matches: {matches}")
            return f"S${matches[0]}"
    
    logger.debug(f"DEBUG: No price patterns matched")
    return None

def save_debug_html(driver, model_name, storage, condition):
    """Save HTML content for debugging purposes"""
    try:
        debug_dir = "debug_html"
        os.makedirs(debug_dir, exist_ok=True)
        safe_filename = f"{model_name}_{storage}_{condition}".replace(" ", "_").replace("/", "_")
        html_path = os.path.join(debug_dir, f"{safe_filename}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.debug(f"DEBUG: Saved HTML to {html_path}")
    except Exception as e:
        logger.debug(f"DEBUG: Failed to save HTML: {e}")

def determine_device_type(model_name):
    """Determine the device type based on the model name."""
    model_lower = model_name.lower()
    
    if any(keyword in model_lower for keyword in ['watch', 'watch series']):
        return 'SmartWatch'
    elif any(keyword in model_lower for keyword in ['macbook', 'mac book']):
        return 'Laptop'
    elif any(keyword in model_lower for keyword in ['airpod', 'air pod']):
        return 'Airpods'
    
    return None  # Return None if no specific device type is detected

def standardize_device_type(device_type):
    """Standardize device type names."""
    if device_type.lower() in ['phone', 'smartphone', 'smartphones']:
        return 'SmartPhone'
    return device_type.capitalize()

def standardize_condition(condition):
    """Standardize condition names."""
    if condition.lower() in ['cracked or chipped', 'cracked', 'chipped']:
        return 'Damaged'
    return condition

def scrape_models(driver, max_models=None):
    """Scrape model links from the current page."""
    logger.info("Scraping model links...")
    
    # Wait a bit longer to ensure page is loaded
    time.sleep(3)
    
    model_selectors = [
        "//ul[contains(@class, 'flex flex-wrap')]/li/a",
        "//div[contains(@class, 'product-grid')]/a",
        "//a[contains(@href, 'buyback-form')]"
    ]
    
    # Try each selector
    models = []
    elements = []
    for selector in model_selectors:
        elements = fast_find_elements(driver, By.XPATH, selector, timeout=2)
        if elements:
            logger.info(f"Found {len(elements)} models with selector: {selector}")
            break
    
    if not elements:
        return []
    
    # Limit the number of models if specified
    if max_models is not None and max_models < len(elements):
        elements = elements[:max_models]
    
    # Extract model information efficiently
    for i, element in enumerate(elements):
        try:
            # Extract URL first (most important)
            url = element.get_attribute("href")
            
            # Quick name extraction - prioritize speed over completeness
            name = None
            try:
                # Try to get text directly from element
                name = element.text.strip()
                if not name:
                    # Try to get from HTML attribute
                    name = element.get_attribute("title") or element.get_attribute("data-name")
            except:
                pass
            
            # If still no name, extract from URL
            if not name:
                name = url.split('/')[-1].split('?')[0].replace('-', ' ')
            
            models.append({"name": name, "url": url})
            logger.info(f"Found model: {name}")
        except Exception as e:
            logger.debug(f"Error extracting model data: {e}")
    
    return models

def process_device_condition(driver, model_name, storage_text, condition):
    """Process a specific device condition and extract trade-in value."""
    logger.info(f"Testing condition: {condition}")
    
    # Find and click screen condition
    condition_selectors = [
        f"//p[contains(@class, 'reb-scr') and contains(text(), '{condition}')]",
        f"//div[contains(@id, 'eval-screen-condition')]//p[contains(text(), '{condition}')]",
        f"//div[contains(text(), 'screen')]//p[contains(text(), '{condition}')]",
        f"//p[contains(text(), '{condition}')]"  # Generic fallback
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
    
    # Click on the condition
    if not safe_click(driver, screen_element):
        logger.warning(f"Could not click on {condition} option")
        return None
    
    # Wait after clicking the screen condition
    time.sleep(2)
    
    # Find and click "Flawless" for housing - try just once
    housing_selectors = [
        "//div[contains(@id, 'eval-housing-condition')]//p[contains(text(), 'Flawless')]",
        "//div[contains(text(), 'housing')]//p[contains(text(), 'Flawless')]"
    ]
    
    for selector in housing_selectors:
        housing_element = fast_find_element(driver, By.XPATH, selector, timeout=0.5)
        if housing_element:
            safe_click(driver, housing_element)
            # Wait after clicking housing condition
            time.sleep(2)
            break
    
    # Select Local Singapore Set if available - quick check only
    local_set_element = fast_find_element(driver, By.XPATH, "//li[contains(text(), 'Local')]", timeout=0.5)
    if local_set_element:
        safe_click(driver, local_set_element)
        # Wait after clicking Local Singapore Set
        time.sleep(2)
    
    # Check for warranty question and select "No" if present
    warranty_yes_selector = "//p[contains(text(), 'original warranty')]/ancestor::div[contains(@class, 'cus-yes-no')]/descendant::li[contains(text(), 'No')]"    
    warranty_yes_element = fast_find_element(driver, By.XPATH, warranty_yes_selector, timeout=0.5)
    if warranty_yes_element:
        logger.info("Found warranty question, selecting 'No'")
        safe_click(driver, warranty_yes_element)
        # Wait after clicking warranty option
        time.sleep(2)
    
    # Check if the button is still disabled
    disabled_button = fast_find_element(driver, By.XPATH, "//button[@disabled]", timeout=0.5)
    if disabled_button:
        logger.info("Quote button is still disabled, checking for other required fields")
        
        # Try to find and select battery health if present
        battery_selectors = [
            "//p[contains(text(), 'Battery Health')]/ancestor::div[contains(@class, 'cus-yes-no')]/descendant::li[contains(text(), '91%')]",
            "//ul[contains(@class, 'cus-battery-health')]/li[1]"  # Select first option
        ]
        for selector in battery_selectors:
            battery_element = fast_find_element(driver, By.XPATH, selector, timeout=0.5)
            if battery_element:
                logger.info("Found battery health question, selecting highest option")
                safe_click(driver, battery_element)
                # Wait after clicking battery health option
                time.sleep(2)
                break
    
    # Click "Get Your Quote" button - try multiple selectors
    quote_button_selectors = [
        "//button[contains(text(), 'Get Your Quote')]",
        "//div[contains(@class, 'cus-btn-des')]//button",
        "//button[contains(@class, 'primary')]",
        "//button"  # Last resort
    ]
    
    quote_button = None
    for selector in quote_button_selectors:
        elements = fast_find_elements(driver, By.XPATH, selector, timeout=0.5)
        if elements:
            quote_button = elements[0]
            break
    
    if not quote_button:
        logger.warning("Could not find 'Get Your Quote' button")
        return None
    
    # Check if button is disabled
    if quote_button.get_attribute("disabled"):
        logger.warning("Quote button is disabled, cannot proceed")
        
        # Try to debug why it's disabled by logging visible form elements
        logger.info("Checking for unfilled required fields...")
        
        # Check for all selectable elements that are visible
        all_selectable = fast_find_elements(driver, By.XPATH, "//li[contains(@class, 'reb-storage')]")
        logger.info(f"Found {len(all_selectable)} selectable options that may need to be filled")
        
        # Try clicking on remaining visible selectors ONE AT A TIME
        # After each click, check if the quote button became enabled
        for element in all_selectable:
            try:
                if element.is_displayed() and "reb-selected" not in element.get_attribute("class"):
                    logger.info(f"Clicking on unselected option: {element.text}")
                    safe_click(driver, element)
                    # Wait after clicking
                    time.sleep(2)
                    
                    # Check if the button is now enabled after this click
                    new_button = fast_find_element(driver, By.XPATH, "//button[contains(text(), 'Get Your Quote')]")
                    if new_button and not new_button.get_attribute("disabled"):
                        quote_button = new_button
                        logger.info(f"Button enabled after selecting: {element.text}")
                        break
            except:
                pass
    
    # Try clicking the button if it's not disabled
    if not quote_button.get_attribute("disabled"):
        if not safe_click(driver, quote_button):
            logger.warning("Still cannot click quote button, skipping")
            return None
    else:
        logger.warning("Quote button still disabled after trying all options, skipping")
        return None
    
    # Wait for price to load
    time.sleep(3)
    
    # Extract price from page content
    page_text = driver.page_source
    price_value = extract_price_from_text(page_text)
    
    # Standardize the condition for output
    standardized_condition = standardize_condition(condition)
    
    if price_value:
        logger.info(f"Found trade-in value: {price_value} for {model_name}, {storage_text}, {standardized_condition}")
        numeric_price = re.sub(r'[^0-9]', '', price_value)
        
        return {
            "model": model_name,
            "storage": storage_text,
            "condition": standardized_condition,
            "trade_in_value": price_value,
            "numeric_value": numeric_price
        }
    else:
        logger.warning(f"Could not find price for {model_name}, {storage_text}, {standardized_condition}")
        return None

def process_all_conditions_efficiently(driver, model_url, model_name):
    """Process all conditions without unnecessary page reloads."""
    logger.info(f"Navigating to model page: {model_url}")
    
    # Navigate to model page
    if not safe_get(driver, model_url):
        logger.warning(f"Failed to load model page: {model_url}")
        return []
    
    # Extract model name from page if necessary
    if not model_name or model_name == "Model":
        try:
            name_element = fast_find_element(driver, By.CLASS_NAME, "product-name-container")
            if name_element:
                model_name = name_element.text.strip()
            else:
                # Extract from URL
                model_name = model_url.split('/')[-1].split('?')[0].replace('-', ' ')
        except:
            # Fallback to URL extraction
            model_name = model_url.split('/')[-1].split('?')[0].replace('-', ' ')
    
    logger.info(f"Processing model: {model_name}")
    
    # Find storage options - grab the first one only
    storage_selectors = [
        "//ul[contains(@class, 'reb-storage-list')]/li[contains(@class, 'reb-storage')]",
        "//div[contains(text(), 'storage')]/following-sibling::div//li"
    ]
    
    storage_text = None
    found_storage = False
    max_storage_attempts = 3
    
    for attempt in range(max_storage_attempts):
        for selector in storage_selectors:
            storage_elements = fast_find_elements(driver, By.XPATH, selector, timeout=0.5)
            if storage_elements:
                # Try to select the first storage option
                storage_element = storage_elements[0]
                storage_text = storage_element.text.strip()
                logger.info(f"Attempting to select storage: {storage_text} (attempt {attempt+1}/{max_storage_attempts})")
                
                if safe_click(driver, storage_element):
                    # Wait after clicking storage option
                    time.sleep(2)
                    found_storage = True
                    break
        
        if found_storage and storage_text:
            logger.info(f"Successfully selected storage: {storage_text}")
            break
            
        # If we couldn't find or select storage, reload and try again
        if attempt < max_storage_attempts - 1:
            logger.warning(f"Failed to select storage, reloading page (attempt {attempt+1}/{max_storage_attempts})")
            if not safe_get(driver, model_url):
                break
            time.sleep(2)  # Wait for page to reload
    
    # If we still couldn't find storage after all attempts, log warning and return empty results
    if not found_storage or not storage_text:
        logger.warning(f"Could not select any storage option after {max_storage_attempts} attempts, skipping model")
        return []
    
    results = []
    conditions = ["Flawless", "Minor Scratches", "Cracked or chipped"]
    
    # Process each condition
    for condition in conditions:
        condition_result = None
        
        # Try up to 3 times for each condition
        for attempt in range(3):
            logger.info(f"Processing condition {condition} (attempt {attempt+1}/3)")
            
            # Reload page for each attempt
            if attempt > 0 or condition != conditions[0]:
                if not safe_get(driver, model_url):
                    logger.warning(f"Failed to reload page for {condition}, skipping")
                    break
                time.sleep(2)  # Wait for page to reload
                
                # Re-select storage
                storage_selected = False
                for selector in storage_selectors:
                    elements = fast_find_elements(driver, By.XPATH, selector, timeout=0.5)
                    if elements:
                        for element in elements:
                            try:
                                if element.text.strip() == storage_text:
                                    logger.info(f"Re-selecting storage: {storage_text}")
                                    if safe_click(driver, element):
                                        time.sleep(2)
                                        storage_selected = True
                                        break
                            except Exception as e:
                                logger.debug(f"Error re-selecting storage: {e}")
                                continue
                    if storage_selected:
                        break
                
                if not storage_selected:
                    logger.warning(f"Failed to re-select storage {storage_text}, skipping this attempt")
                    continue
            
            # Process the condition
            condition_result = process_device_condition(driver, model_name, storage_text, condition)
            
            # If successful, no need for more attempts
            if condition_result and condition_result.get("storage") != "Default":
                # Update storage in result to ensure it matches what we selected
                condition_result["storage"] = storage_text
                break
            
            logger.warning(f"Failed to get valid result for {condition} (attempt {attempt+1}/3)")
        
        # Add successful result to list
        if condition_result and condition_result.get("storage") != "Default":
            results.append(condition_result)
    
    return results

def update_excel_file(new_data, output_file):
    """Update Excel file with new data, creating it if needed."""
    try:
        # Check if file exists and load it
        if os.path.exists(output_file):
            try:
                existing_df = pd.read_excel(output_file)
                # Append new data
                updated_df = pd.concat([existing_df, pd.DataFrame([new_data])], ignore_index=True)
            except Exception as e:
                logger.warning(f"Could not read existing Excel file: {e}")
                # Create new dataframe if file can't be read
                updated_df = pd.DataFrame([new_data])
        else:
            # Create new dataframe if file doesn't exist
            updated_df = pd.DataFrame([new_data])
        
        # Save the updated dataframe
        updated_df.to_excel(output_file, index=False)
        logger.debug(f"Updated Excel file with new data: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to update Excel file: {e}")
        return False

def scrape_devices(driver, device_type, max_devices=None, output_file=None):
    """Scrape devices for a given type (smartphone or tablet)."""
    logger.info(f"Starting to scrape {device_type} data...")
    
    # Standardize device type
    std_device_type = standardize_device_type(device_type)
    
    # Focus on top brands first - most valuable data is usually from these
    priority_brands = ["Apple", "Samsung"]
    # secondary_brands = ["Samsung", "Huawei", "Xiaomi", "Oppo", "OnePlus", "Sony", "LG", 
    #                     "Motorola", "Vivo", "Realme", "Honor", "Nubia", "Nothing"]
    
    secondary_brands = []
    
    all_brands = priority_brands + secondary_brands
    
    results = []
    models_count = 0
    
    # Calculate devices per brand if max_devices specified
    devices_per_brand = None
    if max_devices is not None:
        devices_per_brand = max(1, max_devices // len(priority_brands))
        logger.info(f"Limiting to {max_devices} total devices ({devices_per_brand} per brand)")
    
    # Process priority brands first
    for company in all_brands:
        logger.info(f"Searching for {company} {device_type}s...")
        
        # Skip if we've reached the maximum number of devices
        if max_devices is not None and models_count >= max_devices:
            logger.info(f"Reached maximum of {max_devices} {device_type}s")
            break
        
        # Navigate to brand page
        if not navigate_to_brand_page(driver, device_type, company):
            logger.warning(f"Skipping {company}, couldn't navigate to page")
            continue
        
        # Get models for this brand
        brand_models = scrape_models(driver, devices_per_brand)
        
        if not brand_models:
            logger.warning(f"No models found for {company}, skipping")
            continue
        
        # Process each model
        for model in brand_models:
            if max_devices is not None and models_count >= max_devices:
                break
                
            logger.info(f"Processing {company} {model['name']}...")
            
            # Check if we need to override device type based on model name
            detected_device_type = determine_device_type(model['name'])
            final_device_type = detected_device_type if detected_device_type else std_device_type
            
            # Get trade-in values using efficient method
            trade_in_results = process_all_conditions_efficiently(driver, model["url"], model["name"])
            
            # Add results to our list and update Excel file immediately
            for trade_in in trade_in_results:
                result = {
                    "Country": "Singapore",
                    "Device Type": final_device_type,
                    "Brand": company,
                    "Model": trade_in.get("model", model["name"]),
                    "Capacity": trade_in.get("storage", "Default"),
                    "Color": "N/A",
                    "Launch RRP": "N/A",
                    "Condition": trade_in.get("condition", "N/A"),
                    "Value Type": "Trade-in",
                    "Currency": "SGD",
                    "Value": trade_in.get("numeric_value", ""),
                    "Source": "SG_RV_Source8",
                    "Updated on": time.strftime("%Y-%m-%d"),
                    "Updated by": "",
                    "Comments": "",
                    "URL": ""
                }
                results.append(result)
                
                # Update Excel file immediately after each record
                if output_file:
                    update_excel_file(result, output_file)
            
            models_count += 1
    
    logger.info(f"Completed scraping {len(results)} {device_type} records")
    return results

def main():
    parser = argparse.ArgumentParser(description="Fast scraper for Reebelo trade-in values")
    parser.add_argument("-n", "--number", type=int, help="Number of devices to scrape per category")
    parser.add_argument("-o", "--output", help="Output file path")
    args = parser.parse_args()
    
    # Create output directory
    output_dir = os.environ.get("OUTPUT_DIR", "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Set output file path
    if args.output:
        output_file = args.output
    else:
        date_str = time.strftime("%Y%m%d")
        output_file = os.path.join(output_dir, "SG_RV_Source8.xlsx")
    
    logger.info(f"Results will be saved to: {output_file}")
    
    # Create an empty Excel file if it doesn't exist
    if not os.path.exists(output_file):
        pd.DataFrame(columns=[
            "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
            "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
            "Source", "Updated on", "Updated by", "Comments", "URL"
        ]).to_excel(output_file, index=False)
        logger.info(f"Created new Excel file: {output_file}")
    
    # Setup driver
    driver = setup_driver()
    
    smartphones = []
    tablets = []
    
    try:
        # Scrape smartphones
        logger.info("\n" + "="*50)
        logger.info("SCRAPING SMARTPHONES")
        logger.info("="*50)
        
        smartphones = scrape_devices(driver, "smartphone", args.number, output_file)
        
        # Scrape tablets
        logger.info("\n" + "="*50)
        logger.info("SCRAPING TABLETS")
        logger.info("="*50)
        
        tablets = scrape_devices(driver, "tablet", args.number, output_file)
        
        logger.info(f"All data saved to {output_file}")
        
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
    finally:
        driver.quit()
        logger.info("Script completed")

if __name__ == "__main__":
    main()