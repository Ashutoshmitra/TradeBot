"""
Enhanced Carousell scraper with freeze detection, recovery mechanism, and smart skipping.
- Detects browser freezes and restarts the browser if needed
- Intelligently skips already processed devices (checks at model level for efficiency)
- Implements timeout mechanism to prevent hanging
- Provides detailed statistics on processing results
"""
import os
import time
import random
import pandas as pd
from datetime import datetime
import sys
import traceback
import argparse
import re
import threading
import signal
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Parse command line arguments
parser = argparse.ArgumentParser(description='Scrape device prices from Carousell')
parser.add_argument('-n', '--num_devices', type=int, default=0, 
                    help='Number of devices to scrape. 0 means scrape all devices (default: 0)')
parser.add_argument('-r', '--resume', action='store_true',
                    help='Resume from last processed URL if available')
parser.add_argument('-f', '--force', action='store_true',
                    help='Force processing all devices even if they already exist in the Excel file')
args = parser.parse_args()

# First, ensure undetected-chromedriver is installed
try:
    import undetected_chromedriver as uc
    print("Using undetected-chromedriver for Cloudflare bypass")
except ImportError:
    print("Installing undetected-chromedriver...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "undetected-chromedriver"])
    import undetected_chromedriver as uc
    print("Successfully installed undetected-chromedriver")

# Setup directories
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, 'output')
os.makedirs(output_dir, exist_ok=True)

# Resume file to store last processed URL
resume_file = os.path.join(output_dir, 'resume_state.txt')

# Excel file path
excel_file = os.path.join(output_dir, f'SG_SO_Source1.xlsx')

# Base URL for Carousell Singapore
BASE_URL = "https://www.carousell.sg"

# Global variables for timeout handling
current_operation = "idle"
operation_start_time = None
driver = None
is_frozen = False

# Watchdog timer for detecting freezes
def watchdog_timer():
    global is_frozen, current_operation, operation_start_time, driver
    
    while True:
        if current_operation != "idle" and operation_start_time is not None:
            elapsed_time = time.time() - operation_start_time
            
            if elapsed_time > 30:  # 30 seconds timeout
                print(f"⚠️ TIMEOUT DETECTED: Operation '{current_operation}' is taking too long!")
                is_frozen = True
                
                # Attempt to terminate the driver
                try:
                    if driver is not None:
                        print("Terminating frozen browser...")
                        driver.quit()
                        driver = None
                except:
                    print("Error terminating driver")
                
                # Reset operation state
                current_operation = "idle"
                operation_start_time = None
                
                # Exit the watchdog loop
                break
                
        time.sleep(1)

# Start a new operation with timeout monitoring
def start_operation(operation_name):
    global current_operation, operation_start_time
    current_operation = operation_name
    operation_start_time = time.time()
    print(f"Starting operation: {operation_name}")

# End the current operation
def end_operation():
    global current_operation, operation_start_time
    current_operation = "idle"
    operation_start_time = None

# Initialize or load Excel file with columns matching CompAsia format
def load_excel_file():
    try:
        df = pd.read_excel(excel_file)
        print(f"Loaded existing file: {excel_file}")
        
        # Check and add any missing columns to match CompAsia format
        required_columns = [
            'Country', 'Device Type', 'Brand', 'Model', 'Capacity', 
            'Color', 'Launch RRP', 'Condition', 'Value Type', 
            'Currency', 'Value', 'Source', 'Updated on', 'Updated by', 'Comments'
        ]
        
        for col in required_columns:
            if col not in df.columns:
                df[col] = ""
        
        # Ensure columns are in the correct order
        df = df[required_columns]
        
        return df
        
    except FileNotFoundError:
        # Create new dataframe with columns matching CompAsia format
        df = pd.DataFrame(columns=[
            'Country', 'Device Type', 'Brand', 'Model', 'Capacity', 
            'Color', 'Launch RRP', 'Condition', 'Value Type', 
            'Currency', 'Value', 'Source', 'Updated on', 'Updated by', 'Comments'
        ])
        print(f"Created new data file at: {excel_file}")
        return df

def setup_driver():
    """Create and return an undetected ChromeDriver instance in headless mode"""
    options = uc.ChromeOptions()
    options.add_argument('--enable-javascript')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.page_load_strategy = 'eager'  # Don't wait for all resources to load
    
    # Add headless mode options
    # options.add_argument('--headless=new')  # New headless implementation
    
    # When using headless mode, it's good to set a user agent
    options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36')
    
    # Needed for headless mode to work properly with some websites
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    
    # Create driver with undetected_chromedriver and specify version
    driver = uc.Chrome(
        options=options,
        version_main=135,  # Match your current Chrome version 135
        headless=False      # Also set the headless parameter here for undetected_chromedriver
    )
    
    driver.set_page_load_timeout(30)
    
    # Additional settings that help with headless scraping
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def handle_cloudflare(driver, wait_time=5):
    """Simple cloudflare handling by waiting"""
    print("Waiting for any Cloudflare checks to complete...")
    time.sleep(wait_time)
    return True

def extract_storage_from_text(text):
    """Extract storage size in GB from text"""
    if not text:
        return 128  # Default
    
    # Look for TB first (higher precedence)
    tb_match = re.search(r'(\d+)\s*TB', text, re.IGNORECASE)
    if tb_match:
        return int(tb_match.group(1)) * 1024
    
    # Look for GB
    gb_match = re.search(r'(\d+)\s*GB', text, re.IGNORECASE)
    if gb_match:
        return int(gb_match.group(1))
    
    return 128  # Default if not found

def extract_brand_from_device(device_name):
    """Extract brand from device name"""
    known_brands = [
        "Apple", "Samsung", "Huawei", "Xiaomi", "Oppo", "Vivo", 
        "Google", "OnePlus", "Sony", "LG", "Motorola", "Nokia", 
        "Realme", "Asus", "Poco", "Redmi", "Infinix", "Nothing", "Honor"
    ]
    
    for brand in known_brands:
        if brand.lower() in device_name.lower():
            return brand
    
    # Special cases
    if "iphone" in device_name.lower() or "ipad" in device_name.lower():
        return "Apple"
    if "galaxy" in device_name.lower():
        return "Samsung"
    if "pixel" in device_name.lower():
        return "Google"
    
    return "Unknown"  # Default if no brand detected

def extract_model_from_device(device_name, brand):
    """Extract model from device name by removing the brand if present"""
    if brand != "Unknown" and brand in device_name:
        return device_name.replace(brand, "").strip()
    return device_name

def extract_product_id(url):
    """Extract the unique product ID from a Carousell URL."""
    # Look for patterns like P123456-PV123456-r or similar product identifiers
    match = re.search(r'P\d+-PV\d+-r', url)
    if match:
        return match.group(0)
    return None

def check_if_model_exists(df, model):
    """Check if a specific device model has already been processed"""
    if df.empty:
        return False
    
    # Clean up the model string for comparison by removing extra spaces and common punctuation
    clean_model = model.strip().lower()
    clean_model = re.sub(r'[\s\-\(\)]+', ' ', clean_model).strip()
    
    # Compare with each model in the dataframe using a similar cleaning process
    for existing_model in df['Model'].dropna():
        clean_existing = existing_model.strip().lower()
        clean_existing = re.sub(r'[\s\-\(\)]+', ' ', clean_existing).strip()
        
        # If there's a match, return True
        if clean_model == clean_existing:
            return True
            
    # If we reached here, no match was found
    return False

def safe_find_element(driver, by, value, timeout=5):
    """Safely find an element with timeout"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except Exception as e:
        return None

def click_load_more_button(driver, max_clicks=30):
    """Click the 'Load More' button until it's no longer available"""
    print("Starting to click 'Load More' button...")
    click_count = 0
    product_ids = set()  # Track unique products to verify we're making progress
    consecutive_no_new = 0  # Counter for consecutive clicks with no new content
    
    while click_count < max_clicks:
        # Try to find the Load More button
        load_more_button = None
        
        # Find by text (most reliable method)
        try:
            # Wait for buttons to be present
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "button"))
            )
            
            # Find all buttons
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                try:
                    if "Load more" in button.text:
                        load_more_button = button
                        break
                except StaleElementReferenceException:
                    continue
        except Exception as e:
            print(f"Error searching for Load More button: {e}")
        
        if not load_more_button:
            print("'Load More' button not found. Reached the end of listings.")
            break
        
        # Record the current number of products
        current_links = driver.find_elements(By.TAG_NAME, "a")
        product_count_before = len(product_ids)
        
        # Find new product links
        for link in current_links:
            try:
                href = link.get_attribute("href")
                if href and ("/certified-used-phone-l/" in href or "iphone" in href.lower()) and "viewing_mode=0" in href:
                    product_id = extract_product_id(href)
                    if product_id:
                        product_ids.add(product_id)
            except:
                continue
        
        print(f"Current unique products: {len(product_ids)}")
        
        # Scroll to the button
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
        time.sleep(1)
        
        # Click the button
        try:
            # Try with standard click first
            load_more_button.click()
        except:
            # Fall back to JavaScript click
            driver.execute_script("arguments[0].click();", load_more_button)
        
        print(f"Clicked 'Load More' button ({click_count + 1})")
        click_count += 1
        
        # Wait for new content to load
        time.sleep(3)
        
        # Check if we got new products
        new_count = len(product_ids) - product_count_before
        print(f"Added {new_count} new product IDs after clicking")
        
        # If no new products after 3 consecutive clicks, stop
        if new_count == 0:
            consecutive_no_new += 1
            if consecutive_no_new >= 3:
                print("No new products found after 3 consecutive clicks. Stopping.")
                break
        else:
            consecutive_no_new = 0
    
    print(f"Finished clicking 'Load More' button. Total clicks: {click_count}")
    print(f"Total unique products found: {len(product_ids)}")
    return product_ids

def find_device_links(driver):
    """Find device links on the page using the patterns from scrape.py"""
    valid_links = []
    unique_product_ids = set()
    
    # Wait for content to load
    time.sleep(5)
    
    # Find all links
    links = driver.find_elements(By.TAG_NAME, "a")
    print(f"Found {len(links)} total links on the page")
    
    # Filter for device links using the pattern from scrape.py
    for link in links:
        try:
            href = link.get_attribute("href")
            if not href:
                continue
                
            # Use the key patterns from scrape.py that work well
            if ("/certified-used-phone-l/" in href or "iphone" in href.lower()) and "viewing_mode=0" in href:
                # Extract product ID to avoid duplicates
                product_id = extract_product_id(href)
                if product_id and product_id not in unique_product_ids:
                    unique_product_ids.add(product_id)
                    
                    # Convert relative URL to absolute URL if needed
                    if href.startswith('/'):
                        href = BASE_URL + href
                        
                    valid_links.append(href)
        except Exception as e:
            continue
    
    print(f"Found {len(valid_links)} valid device links")
    return valid_links

def get_page_title(driver):
    """Extract device name from page title or h1 elements"""
    # Try to find the title from h1 elements with a variety of selectors
    selectors = [
        "h1.D_kQ", "h1.D_jN", "h1.D_jS", "h1", ".D_aMY h1", 
        "[data-testid='listing-title']", "h1.D_kQ.D_kV.D_kY.D_lc"
    ]
    
    for selector in selectors:
        try:
            element = driver.find_element(By.CSS_SELECTOR, selector)
            if element and element.text.strip():
                return element.text.strip()
        except:
            pass
    
    # If all selectors fail, try extracting from title
    try:
        page_title = driver.title
        if " - " in page_title:
            return page_title.split(" - ")[0].strip()
        else:
            return page_title.strip()
    except:
        pass
    
    # If no name found, try to extract from URL
    try:
        url = driver.current_url.lower()
        if "iphone" in url:
            return "iPhone (Unknown Model)"
    except:
        pass
    
    return "Unknown Device"

def get_price(driver):
    """Get the price from the page using various selectors"""
    price_selectors = [
        'span.D_jp.D_jq.D_jt.D_jx.D_j_.D_jB.D_aJr.D_jJ',  # Price in review section
        'span.D_jj.D_jk.D_jn.D_jr.D_ju.D_jw.D_aJn.D_jC',  # Regular price format
        'h2.D_aJn.D_jN',  # Discounted price format
        'h2.D_kQ.D_kV.D_kY.D_lc',  # Main product title (might include price)
        'div.D_abR h2',  # Any h2 within price container
        'div.D_abR span:not(s)',  # Any non-strikethrough span in price container
        'div[id*="price"] span',  # Any span in a div with 'price' in the ID
        '*[data-testid="listing-price"]',  # Element with listing-price test ID
        'span[class*="price"]',  # Any span with 'price' in class
        'span.D_jp.D_jq.D_jt.D_jx.D_j_.D_jB.D_aJr.D_jK'  # Another price format
    ]
    
    # Try JavaScript method first since it's more reliable
    try:
        js_price = driver.execute_script("""
            // Look for price elements with S$ or $ in them
            const elements = document.querySelectorAll('span, h2, p, div');
            for (const el of elements) {
                if (el.textContent && (el.textContent.includes('S$') || 
                   (el.textContent.includes('$') && !el.textContent.includes('*')))) {
                    return el.textContent.trim();
                }
            }
            return '';
        """)
        
        if js_price and ('S$' in js_price or '$' in js_price):
            # Extract numeric value
            price_text = js_price.replace('S$', '').replace('$', '').replace(',', '')
            try:
                price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
                print(f"Found price via JavaScript: S${price}")
                return price
            except:
                pass
    except:
        pass
    
    # Try CSS selectors
    for selector in price_selectors:
        try:
            element = driver.find_element(By.CSS_SELECTOR, selector)
            if element:
                price_text = element.text.strip()
                if price_text and any(c.isdigit() for c in price_text):
                    # Extract numeric value (handle S$XXX format)
                    price_text = price_text.replace('S$', '').replace('$', '').replace(',', '')
                    try:
                        price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
                        print(f"Found price: S${price} using selector: {selector}")
                        return price
                    except:
                        pass
        except:
            pass
    
    return None

def find_storage_options(driver):
    """Find all storage options on the page"""
    storage_options = []
    
    # First try to find the storage container
    storage_container = None
    container_selectors = [
        'div[id*="storage"]',
        'div[data-testid="storage-selector"]',
        'div.D_afa',  # Container for options in Realme example
        '//div[contains(., "Storage") and .//button]',  # XPath finding text + buttons
    ]
    
    for selector in container_selectors:
        try:
            if selector.startswith('//'):
                # Handle XPath
                storage_container = driver.find_element(By.XPATH, selector)
            else:
                storage_container = driver.find_element(By.CSS_SELECTOR, selector)
                
            if storage_container:
                print("Found storage container")
                break
        except:
            pass
    
    if not storage_container:
        # If no container found, extract storage from page title
        device_name = get_page_title(driver)
        storage_gb = extract_storage_from_text(device_name)
        storage_options.append({"value": f"{storage_gb}GB", "element": None})
        return storage_options
    
    # Find storage buttons in the container
    try:
        # Look for buttons
        buttons = storage_container.find_elements(By.TAG_NAME, "button")
        
        for button in buttons:
            try:
                # Get button text - either directly or via span
                spans = button.find_elements(By.TAG_NAME, "span")
                if spans:
                    button_text = spans[0].text.strip()
                else:
                    button_text = button.text.strip()
                
                # If the button text contains GB or TB, it's a storage option
                if "GB" in button_text or "TB" in button_text or "gb" in button_text.lower() or "tb" in button_text.lower():
                    storage_options.append({"value": button_text, "element": button})
                    print(f"Found storage option: {button_text}")
            except:
                pass
    except Exception as e:
        print(f"Error finding storage buttons: {e}")
    
    # If no storage options found, extract from title
    if not storage_options:
        device_name = get_page_title(driver)
        storage_gb = extract_storage_from_text(device_name)
        storage_options.append({"value": f"{storage_gb}GB", "element": None})
    
    return storage_options

def find_condition_options(driver):
    """Find all condition options on the page"""
    condition_options = []
    
    # First try to find the condition container
    condition_container = None
    container_selectors = [
        'div[id*="condition"]',
        'div[data-testid="condition-selector"]',
        '//div[contains(., "Condition") and .//button]',  # XPath for text + buttons
    ]
    
    for selector in container_selectors:
        try:
            if selector.startswith('//'):
                # Handle XPath
                condition_container = driver.find_element(By.XPATH, selector)
            else:
                condition_container = driver.find_element(By.CSS_SELECTOR, selector)
                
            if condition_container:
                print("Found condition container")
                break
        except:
            pass
    
    if not condition_container:
        # Default condition if container not found
        condition_options.append({"value": "Unknown", "element": None})
        return condition_options
    
    # Find condition buttons in the container
    try:
        # Get all buttons
        buttons = condition_container.find_elements(By.TAG_NAME, "button")
        
        for button in buttons:
            try:
                # Skip buttons that look like help buttons
                class_attr = button.get_attribute("class")
                if class_attr and "help" in class_attr.lower():
                    continue
                
                # Get button text - either directly or via span
                spans = button.find_elements(By.TAG_NAME, "span")
                if spans:
                    button_text = spans[0].text.strip()
                else:
                    button_text = button.text.strip()
                
                # Skip empty text or just symbols
                if button_text and len(button_text) > 1 and "?" not in button_text:
                    condition_options.append({"value": button_text, "element": button})
                    print(f"Found condition option: {button_text}")
            except:
                pass
    except Exception as e:
        print(f"Error finding condition buttons: {e}")
    
    # If no condition options found, use default
    if not condition_options:
        condition_options.append({"value": "Unknown", "element": None})
    
    return condition_options

def get_device_color(driver):
    """Extract color information from the page"""
    try:
        # Try to find color text next to "Color" label
        color_spans = driver.find_elements(By.XPATH, "//span[contains(text(), 'Color')]/following-sibling::span")
        if color_spans:
            return color_spans[0].text.strip()
        
        # Try another approach with div containing color info
        color_divs = driver.find_elements(By.CSS_SELECTOR, "div[id*='color']")
        if color_divs:
            for div in color_divs:
                spans = div.find_elements(By.TAG_NAME, "span")
                for i, span in enumerate(spans):
                    if span.text.strip() == "Color" and i+1 < len(spans):
                        return spans[i+1].text.strip()
        
        # Try extracting from title
        title = get_page_title(driver)
        known_colors = ["Gold", "Silver", "Black", "White", "Blue", "Green", "Purple", 
                       "Red", "Gray", "Graphite", "Sierra Blue", "Pacific Blue",
                       "Midnight", "Starlight", "Pink", "Yellow", "Orange", "Monet Purple"]
        
        for color in known_colors:
            if color.lower() in title.lower():
                return color
                
    except Exception as e:
        print(f"Error getting color: {e}")
    
    return ""  # Default if not found

def map_condition_text(condition_text):
    """Map Carousell condition text to CompAsia format"""
    condition_lower = condition_text.lower()
    
    if "brand" in condition_lower or "new" in condition_lower:
        return "Brand New"
    elif "like new" in condition_lower or "excellent" in condition_lower:
        return "Excellent"
    elif "lightly" in condition_lower or "good" in condition_lower:
        return "Good"
    elif "well" in condition_lower or "fair" in condition_lower:
        return "Fair"
    else:
        return condition_text  # Keep original if no mapping found

def save_last_processed_url(url):
    """Save the last successfully processed URL for resuming later"""
    with open(resume_file, 'w') as f:
        f.write(url)
    print(f"Saved resume state: {url}")

def get_last_processed_url():
    """Get the last successfully processed URL"""
    if os.path.exists(resume_file):
        with open(resume_file, 'r') as f:
            url = f.read().strip()
            if url:
                print(f"Found resume state: {url}")
                return url
    return None

def process_device_listing(driver, url, df):
    """Process a device listing page directly"""
    global is_frozen
    device_data = []
    
    try:
        # Convert relative URL to absolute URL if needed
        if url.startswith('/'):
            full_url = BASE_URL + url
        else:
            full_url = url
            
        print(f"Navigating to: {full_url}")
        try:
            start_operation("navigate_to_url")
            driver.get(full_url)
            end_operation()
            
            # If we got here, the browser didn't freeze
            time.sleep(5)  # Wait for page to load
        except TimeoutException:
            print("Page load timed out, but continuing anyway")
            driver.execute_script("window.stop();")  # Stop page loading
        except Exception as e:
            print(f"Error navigating to URL: {e}")
            if is_frozen:
                print("Browser freeze detected, restarting...")
                is_frozen = False
                return []  # Return empty to trigger retry
        
        # Check if browser froze during operation
        if is_frozen:
            print("Browser freeze detected, restarting...")
            is_frozen = False
            return []
        
        # Get device name
        start_operation("get_page_title")
        device_name = get_page_title(driver)
        end_operation()
        print(f"Processing device: {device_name}")
        
        # Extract brand from device name
        brand = extract_brand_from_device(device_name)
        
        # Extract model name
        model = extract_model_from_device(device_name, brand)
        
        # Check if this model already exists in the Excel file (unless force flag is set)
        if not args.force and check_if_model_exists(df, model):
            print(f"📋 Model '{model}' already exists in the Excel file. Skipping this device completely.")
            # Save the URL as processed even though we're skipping it
            save_last_processed_url(url)
            # Return a special flag for stats tracking
            return ["SKIPPED_EXISTING_MODEL"]
        
        # Determine device type
        device_type = "Tablet" if any(keyword in device_name.lower() for keyword in ["ipad", "tab", "tablet"]) else "SmartPhone"
        
        # Get device color
        color = get_device_color(driver)
        
        # Get initial price
        start_operation("get_initial_price")
        initial_price = get_price(driver)
        end_operation()
        
        if not initial_price:
            print("Could not find price. Skipping device.")
            return []
        
        # Get storage options
        start_operation("find_storage_options")
        storage_options = find_storage_options(driver)
        end_operation()
        
        # Get condition options
        start_operation("find_condition_options")
        condition_options = find_condition_options(driver)
        end_operation()
        
        # Check if browser froze during operations
        if is_frozen:
            print("Browser freeze detected, restarting...")
            is_frozen = False
            return []
        
        # Process all combinations of storage and condition
        for storage_option in storage_options:
            storage_text = storage_option["value"]
            storage_button = storage_option["element"]
            storage_gb = extract_storage_from_text(storage_text)
            
            # Determine the capacity string format
            capacity_display = f"{storage_gb}GB"
            if storage_gb == 1024:
                capacity_display = "1TB"
            elif storage_gb == 2048:
                capacity_display = "2TB"
            
            # Click on storage button if available
            if storage_button:
                try:
                    print(f"Clicking on storage: {storage_text}")
                    start_operation(f"click_storage_{storage_text}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", storage_button)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", storage_button)
                    end_operation()
                    time.sleep(2)  # Wait for page to update
                except Exception as e:
                    print(f"Error clicking storage button: {e}")
                    end_operation()
            
            # Get current price after storage selection (might have changed)
            start_operation("get_price_after_storage")
            current_price = get_price(driver) or initial_price
            end_operation()
            
            for condition_option in condition_options:
                condition_text = condition_option["value"]
                condition_button = condition_option["element"]
                
                # Map condition text to CompAsia format
                mapped_condition = map_condition_text(condition_text)
                
                # Since we already checked if the model exists in the Excel file at the beginning,
                # we don't need to check for each specific configuration here
                
                # Click on condition button if available
                if condition_button:
                    try:
                        print(f"Clicking on condition: {condition_text}")
                        start_operation(f"click_condition_{condition_text}")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", condition_button)
                        time.sleep(0.5)
                        driver.execute_script("arguments[0].click();", condition_button)
                        end_operation()
                        time.sleep(2)  # Wait for page to update
                    except Exception as e:
                        print(f"Error clicking condition button: {e}")
                        end_operation()
                        # If we had an error, check if browser froze
                        if is_frozen:
                            print("Browser freeze detected, restarting...")
                            is_frozen = False
                            return []
                
                # Get price after condition selection
                start_operation("get_final_price")
                final_price = get_price(driver) or current_price
                end_operation()
                
                # Don't add if we couldn't get a price
                if not final_price:
                    print(f"Could not find price for {storage_text} - {mapped_condition}. Skipping.")
                    continue
                
                # Check if this is a duplicate entry
                is_duplicate = False
                for entry in device_data:
                    if (entry['Capacity'] == capacity_display and 
                        entry['Condition'] == mapped_condition):
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    # Get current date
                    today = datetime.now().strftime("%Y-%m-%d")
                    
                    device_data.append({
                        'Country': 'Singapore',
                        'Device Type': device_type,
                        'Brand': brand,
                        'Model': model,
                        'Capacity': capacity_display,
                        'Color': color,
                        'Launch RRP': "",
                        'Condition': mapped_condition,
                        'Value Type': 'Sell-Off',
                        'Currency': 'SGD',
                        'Value': final_price,
                        'Source': 'SG_SO_Source1',
                        'Updated on': today,
                        'Updated by': '',
                        'Comments': ''
                    })
                    print(f"Extracted: {device_name} - {capacity_display} - {mapped_condition} - S${final_price}")
                else:
                    print(f"Skipping duplicate entry: {capacity_display} - {mapped_condition}")
        
        # Save the last successfully processed URL
        save_last_processed_url(url)
        
        return device_data
    
    except Exception as e:
        print(f"Error processing device: {e}")
        traceback.print_exc()
        
        # Check if the browser froze
        if is_frozen:
            print("Browser freeze detected during exception, restarting...")
            is_frozen = False
            return []
            
        return []

def restart_browser():
    """Restart the browser completely"""
    global driver
    
    print("🔄 Restarting browser...")
    
    # Clean up old driver if it exists
    try:
        if driver is not None:
            driver.quit()
    except:
        print("Error closing old driver")
    
    # Create a new driver
    try:
        driver = setup_driver()
        print("Browser restarted successfully")
        return driver
    except Exception as e:
        print(f"Error restarting browser: {e}")
        # Emergency sleep to allow system to recover
        time.sleep(30)
        driver = setup_driver()
        return driver

def main():
    """Main function to scrape device prices"""
    global driver, is_frozen
    
    # Load Excel file
    df = load_excel_file()
    
    # Setup driver
    print("Setting up undetected ChromeDriver...")
    driver = setup_driver()
    
    # Start the watchdog thread
    watchdog_thread = threading.Thread(target=watchdog_timer, daemon=True)
    watchdog_thread.start()
    
    # If resume flag is set, try to get last processed URL
    last_processed_url = None
    resume_from_index = 0
    if args.resume:
        last_processed_url = get_last_processed_url()
    
    # Stats tracking
    skipped_devices = 0
    processed_devices = 0
    
    try:
        # Navigate directly to the target page
        print("Navigating to certified mobiles page...")
        start_operation("navigate_to_main_page")
        driver.get("https://www.carousell.sg/smart_render/?type=market-landing-page&name=ap-certified-mobiles")
        end_operation()
        
        # Simple wait for page to load
        time.sleep(5)
        
        # Check if browser froze
        if is_frozen:
            print("Browser froze during initial navigation, restarting...")
            driver = restart_browser()
            is_frozen = False
            
            # Try again
            start_operation("navigate_to_main_page_retry")
            driver.get("https://www.carousell.sg/smart_render/?type=market-landing-page&name=ap-certified-mobiles")
            end_operation()
            time.sleep(5)
        
        # Simple Cloudflare handling
        handle_cloudflare(driver)
        
        # Click Load More button to load all listings
        print("Loading all device listings...")
        start_operation("click_load_more")
        click_load_more_button(driver, max_clicks=30)
        end_operation()
        
        # Check if browser froze
        if is_frozen:
            print("Browser froze while loading listings, restarting...")
            driver = restart_browser()
            is_frozen = False
            
            # Try again
            start_operation("navigate_to_main_page_after_freeze")
            driver.get("https://www.carousell.sg/smart_render/?type=market-landing-page&name=ap-certified-mobiles")
            end_operation()
            time.sleep(5)
            
            # Handle Cloudflare again
            handle_cloudflare(driver)
            
            # Try loading listings again
            start_operation("click_load_more_retry")
            click_load_more_button(driver, max_clicks=30)
            end_operation()
        
        # Find device links using the pattern from scrape.py
        print("Finding device links...")
        start_operation("find_device_links")
        card_urls = find_device_links(driver)
        end_operation()
        
        # Remove duplicates
        card_urls = list(set(card_urls))
        print(f"Found {len(card_urls)} unique device links")
        
        # If resuming, find the index of the last processed URL
        if last_processed_url and last_processed_url in card_urls:
            resume_from_index = card_urls.index(last_processed_url) + 1
            print(f"Resuming from URL index {resume_from_index} of {len(card_urls)}")
        else:
            resume_from_index = 0
        
        # Apply device limit from command-line argument
        if args.num_devices > 0:
            max_index = resume_from_index + args.num_devices
            if max_index < len(card_urls):
                print(f"Limiting to {args.num_devices} devices starting from index {resume_from_index}")
                card_urls = card_urls[resume_from_index:max_index]
            else:
                card_urls = card_urls[resume_from_index:]
        else:
            # Just apply the resume index
            card_urls = card_urls[resume_from_index:]
        
        # Process each device
        for i, card_url in enumerate(card_urls):
            print(f"\nProcessing device {i+1}/{len(card_urls)} (overall: {resume_from_index + i + 1})")
            print(f"URL: {card_url}")
            
            # Process this device with retries
            device_data = []
            retry_count = 0
            max_retries = 3
            success = False
            
            while not success and retry_count < max_retries:
                try:
                    # Check if browser is still responsive before processing
                    if driver is None or is_frozen:
                        print("Browser needs to be restarted before processing")
                        driver = restart_browser()
                        is_frozen = False
                    
                    # Process the device
                    device_data = process_device_listing(driver, card_url, df)
                    
                    # If browser froze during processing, retry
                    if is_frozen or driver is None:
                        print("Browser froze during processing, retrying...")
                        driver = restart_browser()
                        is_frozen = False
                        retry_count += 1
                        continue
                    
                    # Consider success only if we got data and no freeze occurred
                    if device_data:
                        success = True
                    else:
                        print("No data extracted, considering as failure")
                        retry_count += 1
                except Exception as e:
                    retry_count += 1
                    print(f"Error processing device (attempt {retry_count}/{max_retries}): {e}")
                    
                    # Check if browser froze
                    if is_frozen or driver is None:
                        print("Browser froze during exception, restarting...")
                        driver = restart_browser()
                        is_frozen = False
                    
                    if retry_count < max_retries:
                        print("Retrying after a short delay...")
                        time.sleep(5)
                
                # Check for our special skipped flag
                if device_data and device_data[0] == "SKIPPED_EXISTING_MODEL":
                    skipped_devices += 1
                # Update Excel file if we got data
                elif device_data:
                    new_rows_df = pd.DataFrame(device_data)
                    
                    # Handle empty df warning
                    if not df.empty or not new_rows_df.empty:
                        df = pd.concat([df, new_rows_df], ignore_index=True)
                        # Only drop duplicates if we actually have rows
                        if not df.empty:
                            df.drop_duplicates(subset=['Model', 'Capacity', 'Condition'], keep='last', inplace=True)
                    else:
                        df = new_rows_df
                        
                    df.to_excel(excel_file, index=False)
                    print(f"Updated Excel file with {len(device_data)} new entries")
                    processed_devices += 1
                else:
                    print("No data extracted for this device after all retries")
            
            # Add random delay between processing
            delay = random.uniform(2, 4)
            print(f"Waiting {delay:.1f} seconds before next device...")
            time.sleep(delay)
        
    except Exception as e:
        print(f"Error in main function: {e}")
        traceback.print_exc()
    
    finally:
        # End the watchdog operation
        current_operation = "idle"
        
        # Save final data
        try:
            if 'df' in locals() and not df.empty:
                df.to_excel(excel_file, index=False)
                print(f"Final data saved to {excel_file}")
                
                # Print summary
                print("\n📊 DATA SUMMARY:")
                print(f"Total unique models in database: {df['Model'].nunique()}")
                print(f"Total entries in database: {len(df)}")
                print(f"\n📊 SESSION SUMMARY:")
                print(f"Models processed in this session: {processed_devices}")
                print(f"Models skipped (already in database): {skipped_devices}")
                print(f"Total devices examined: {processed_devices + skipped_devices}")
        except Exception as e:
            print(f"Error saving final data: {e}")
        
        # Close driver
        try:
            if driver is not None:
                driver.quit()
                print("Driver closed")
        except:
            print("Driver already closed")

if __name__ == "__main__":
    main()