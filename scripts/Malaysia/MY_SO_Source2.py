"""
This script scrapes device prices from 3cat.my website for Malaysian sell-off prices.
It navigates to the website, finds product links, and extracts storage options and prices.
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
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# Parse command line arguments
parser = argparse.ArgumentParser(description='Scrape device prices from 3cat.my')
parser.add_argument('-n', '--num_devices', type=int, default=0, 
                    help='Number of devices to scrape. 0 means scrape all devices (default: 0)')
parser.add_argument('-o', '--output', type=str, default=None,
                    help='Output Excel file path (default: output/MY_SO_Source2.xlsx)')
args = parser.parse_args()

# Setup directories
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, 'output')
os.makedirs(output_dir, exist_ok=True)

# Excel file path
if args.output:
    excel_file = args.output
else:
    excel_file = os.path.join(output_dir, f'MY_SO_Source2.xlsx')
# Base URL for 3cat.my
BASE_URL = "https://3cat.my"

# Initialize or load Excel file with columns matching CompAsia format
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
    
except FileNotFoundError:
    # Create new dataframe with columns matching CompAsia format
    df = pd.DataFrame(columns=[
        'Country', 'Device Type', 'Brand', 'Model', 'Capacity', 
        'Color', 'Launch RRP', 'Condition', 'Value Type', 
        'Currency', 'Value', 'Source', 'Updated on', 'Updated by', 'Comments'
    ])
    print(f"Created new data file at: {excel_file}")

def setup_driver():
    """Create and return a regular Chrome WebDriver instance with headless mode enabled"""
    options = Options()
    
    # Add headless mode
    options.add_argument('--headless=new')  # Use the new headless implementation
    
    # Keep the existing options
    options.add_argument('--enable-javascript')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    
    # Create driver with ChromeDriverManager
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    driver.set_page_load_timeout(30)
    
    return driver

def should_process_url(url):
    """Check if URL should be processed (skip Mac devices and collection pages)"""
    # Patterns to skip
    skip_patterns = [
        # Mac devices
        '/mac/', '/imac/', '/macbook/', '/cat/used-mac', '/cat/used-imac',
        # Collection pages
        '/cat/used-', 
        '/collection/', 
        '/used-apple-watch/',
        '/used-iphone$', '/used-ipad$'  # Ensure these are collection links not specific models
    ]
    return not any(pattern in url.lower() for pattern in skip_patterns)

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

def extract_model_from_url(url):
    """Extract model directly from URL for more accurate model names"""
    model = ""
    
    # Skip if URL doesn't contain used-
    if "used-" not in url:
        return model
    
    # Get the part after used- and before any trailing slash
    path_parts = url.split('/')
    for part in path_parts:
        if part.startswith('used-'):
            # Remove "used-" prefix
            model_part = part[5:]
            
            # Handle special cases (iPad Air with M2, etc.)
            if "ipad-air-6th-gen" in model_part:
                return "iPad Air 6th Gen"
            elif "ipad-pro-11-inch-m4" in model_part:
                return "iPad Pro 11-inch M4"
            
            # General case: replace hyphens with spaces and title case
            segments = model_part.split('-')
            
            # Process iPhone models
            if "iphone" in segments[0]:
                iphone_model = "iPhone"
                for i in range(1, len(segments)):
                    iphone_model += " " + segments[i].title()
                return iphone_model.strip()
            
            # Process iPad models
            if "ipad" in segments[0]:
                ipad_model = "iPad"
                # Check for Pro/Air/Mini
                model_type = ""
                version = ""
                for i in range(1, len(segments)):
                    if segments[i] in ["pro", "air", "mini"]:
                        model_type = segments[i].title()
                    elif segments[i].isdigit() or segments[i].endswith("th") or segments[i].endswith("nd") or segments[i].endswith("rd"):
                        version = segments[i]
                
                if model_type:
                    ipad_model += " " + model_type
                if version:
                    ipad_model += " " + version.title()
                
                return ipad_model.strip()
            
            # Generic case
            return model_part.replace('-', ' ').title()
    
    return model

def determine_device_type(device_name):
    """Determine device type based on device name"""
    device_name_lower = device_name.lower()
    
    if "watch" in device_name_lower:
        return "SmartWatch"
    elif "ipad" in device_name_lower or "tab" in device_name_lower or "tablet" in device_name_lower:
        return "Tablet"
    else:
        return "SmartPhone"

def safe_find_element(driver, by, value, timeout=5):
    """Safely find an element with timeout"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except Exception as e:
        return None

def find_product_links(driver):
    """Find all product links on the page"""
    valid_links = []
    
    # Wait for content to load
    time.sleep(5)
    
    # Method 1: Find all links with '/used' in them
    links = driver.find_elements(By.TAG_NAME, "a")
    print(f"Found {len(links)} total links on the page")
    
    for link in links:
        try:
            href = link.get_attribute("href")
            if not href:
                continue
            
            # Check for product links - look for patterns like /used-* or other product indicators
            if "/used-" in href and href not in valid_links:
                valid_links.append(href)
        except Exception as e:
            continue
    
    # Method 2: Try to find all product cards and extract links
    try:
        # Find product cards using various selectors
        product_cards = driver.find_elements(By.CSS_SELECTOR, ".product-card")
        if not product_cards:
            product_cards = driver.find_elements(By.CSS_SELECTOR, "[data-carousel-target='card']")
        
        for card in product_cards:
            try:
                link_element = card.find_element(By.TAG_NAME, "a")
                href = link_element.get_attribute("href")
                if href and "/used-" in href and href not in valid_links:
                    valid_links.append(href)
            except:
                pass
    except:
        pass
    
    # Method 3: Find all "More Details" buttons and get their parent links
    try:
        detail_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'More Details')]")
        for button in detail_buttons:
            try:
                # Find closest parent a tag
                parent = button
                for _ in range(5):  # Look up to 5 levels up
                    parent = parent.find_element(By.XPATH, "..")
                    try:
                        links = parent.find_elements(By.TAG_NAME, "a")
                        for link in links:
                            href = link.get_attribute("href")
                            if href and "/used-" in href and href not in valid_links:
                                valid_links.append(href)
                        if links:
                            break
                    except:
                        continue
            except:
                pass
    except:
        pass
    
    # Method 4: Execute JavaScript to find all product links
    try:
        js_links = driver.execute_script("""
            const links = [];
            document.querySelectorAll('a').forEach(link => {
                const href = link.getAttribute('href');
                if (href && href.includes('/used-')) {
                    links.push(href);
                }
            });
            return links;
        """)
        
        for href in js_links:
            if href not in valid_links:
                valid_links.append(href)
    except:
        pass
    
    # Method 5: Scroll the page to load more content and find links again
    try:
        # Scroll down the page in increments
        for _ in range(5):
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(1)
            
            # Find links after scrolling
            links = driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if href and "/used-" in href and href not in valid_links:
                        valid_links.append(href)
                except:
                    continue
    except:
        pass
    
    # Ensure all links are absolute URLs
    for i, link in enumerate(valid_links):
        if not link.startswith('http'):
            valid_links[i] = BASE_URL + link
    
    print(f"Found {len(valid_links)} valid device links")
    return valid_links

def get_page_title(driver):
    """Extract device name from page title or h1 elements"""
    # Try to find the title from h1 elements
    selectors = [
        "h1.product-name", "h1", ".product-info h1", 
        "[data-testid='product-title']", "div.product-title"
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
        if "used-" in url:
            device_part = url.split("used-")[1].split("/")[0]
            return "Used " + device_part.replace("-", " ").title()
    except:
        pass
    
    return "Unknown Device"

def extract_price_from_text(text):
    """Extract numeric price from text containing RM"""
    if not text:
        return None
    
    # Try to find RM followed by digits, optionally with commas and decimal point
    price_match = re.search(r'RM\s*([\d,]+(?:\.\d+)?)', text)
    if price_match:
        # Remove commas and convert to float
        price_text = price_match.group(1).replace(',', '')
        try:
            return float(price_text)
        except:
            pass
    
    return None

def find_storage_options(driver):
    """Find all storage options on the page"""
    storage_options = []
    
    # Try to find the storage section
    try:
        # Method 1: Find storage section by looking for "Storage:" text
        storage_sections = driver.find_elements(By.XPATH, "//div[contains(text(), 'Storage:')]/parent::div")
        
        if storage_sections:
            for section in storage_sections:
                buttons = section.find_elements(By.TAG_NAME, "button")
                for button in buttons:
                    try:
                        button_text = button.text.strip()
                        storage_match = re.search(r'(\d+\s*[GT]B)', button_text)
                        if storage_match:
                            storage_text = storage_match.group(1)
                            
                            # Try to find price in the button
                            price = None
                            price_elements = button.find_elements(By.XPATH, ".//*[contains(text(), 'RM')]")
                            if price_elements:
                                for price_elem in price_elements:
                                    extracted_price = extract_price_from_text(price_elem.text)
                                    if extracted_price:
                                        price = extracted_price
                                        break
                            
                            storage_options.append({
                                "value": storage_text,
                                "element": button,
                                "price": price
                            })
                    except:
                        pass
        
        # Method 2: If no storage sections found, look for buttons with GB text
        if not storage_options:
            storage_container = driver.find_element(By.CSS_SELECTOR, "div.product-attributes")
            buttons = storage_container.find_elements(By.TAG_NAME, "button")
            
            for button in buttons:
                try:
                    button_text = button.text.strip()
                    if "GB" in button_text or "TB" in button_text:
                        storage_match = re.search(r'(\d+\s*[GT]B)', button_text)
                        if storage_match:
                            storage_text = storage_match.group(1)
                            
                            # Try to find price in the button
                            price = None
                            price_elements = button.find_elements(By.XPATH, ".//*[contains(text(), 'RM')]")
                            if price_elements:
                                for price_elem in price_elements:
                                    extracted_price = extract_price_from_text(price_elem.text)
                                    if extracted_price:
                                        price = extracted_price
                                        break
                            
                            storage_options.append({
                                "value": storage_text,
                                "element": button,
                                "price": price
                            })
                except:
                    pass
    except:
        pass
    
    # Method a last attempt to find storage options
    if not storage_options:
        try:
            # Direct approach - find all buttons with storage text
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for button in buttons:
                try:
                    button_text = button.text.strip()
                    if "GB" in button_text or "TB" in button_text:
                        storage_match = re.search(r'(\d+\s*[GT]B)', button_text)
                        if storage_match:
                            storage_text = storage_match.group(1)
                            
                            # Try to find price in the button
                            price = None
                            if "RM" in button_text:
                                extracted_price = extract_price_from_text(button_text)
                                if extracted_price:
                                    price = extracted_price
                            
                            storage_options.append({
                                "value": storage_text,
                                "element": button,
                                "price": price
                            })
                except:
                    pass
        except:
            pass
    
    # Special case for Watches which don't have storage options
    if not storage_options and "watch" in driver.page_source.lower():
        storage_options.append({
            "value": "",
            "element": None,
            "price": None
        })
    
    # If still no storage options found, look for it in the device name
    if not storage_options:
        device_name = get_page_title(driver)
        if "GB" in device_name or "TB" in device_name:
            storage_match = re.search(r'(\d+\s*[GT]B)', device_name)
            if storage_match:
                storage_text = storage_match.group(1)
                storage_options.append({
                    "value": storage_text,
                    "element": None,
                    "price": None
                })
        else:
            # Default option if no storage info found
            storage_options.append({
                "value": "",
                "element": None,
                "price": None
            })
    
    return storage_options

def get_connectivity_prices(driver):
    """Get both WiFi and WiFi+Cellular prices directly"""
    wifi_price = None
    cellular_price = None
    
    # Method 1: Look for buttons with connectivity options
    try:
        # Find WiFi price
        wifi_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'WiFi') and not(contains(., 'Cellular'))]")
        for button in wifi_buttons:
            price_elements = button.find_elements(By.XPATH, ".//*[contains(text(), 'RM')]")
            if price_elements:
                for elem in price_elements:
                    price = extract_price_from_text(elem.text)
                    if price:
                        wifi_price = price
                        break
            
            # If price wasn't found in child elements, check button text itself
            if not wifi_price and "RM" in button.text:
                price = extract_price_from_text(button.text)
                if price:
                    wifi_price = price
        
        # Find WiFi+Cellular price
        cellular_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'WiFi') and contains(., 'Cellular')]")
        for button in cellular_buttons:
            price_elements = button.find_elements(By.XPATH, ".//*[contains(text(), 'RM')]")
            if price_elements:
                for elem in price_elements:
                    price = extract_price_from_text(elem.text)
                    if price:
                        cellular_price = price
                        break
            
            # If price wasn't found in child elements, check button text itself
            if not cellular_price and "RM" in button.text:
                price = extract_price_from_text(button.text)
                if price:
                    cellular_price = price
    except:
        pass
    
    # Method 2: Look for direct price elements near connectivity text
    if not wifi_price or not cellular_price:
        try:
            # Find price elements next to connectivity options
            price_sections = driver.find_elements(By.XPATH, "//div[contains(text(), 'Connectivity:')]/following::div[1]")
            if price_sections:
                for section in price_sections:
                    wifi_elements = section.find_elements(By.XPATH, "//button[contains(., 'WiFi') and not(contains(., 'Cellular'))]//div[contains(@class, 'lastAttribute')]")
                    for elem in wifi_elements:
                        price = extract_price_from_text(elem.text)
                        if price:
                            wifi_price = price
                            break
                    
                    cellular_elements = section.find_elements(By.XPATH, "//button[contains(., 'WiFi') and contains(., 'Cellular')]//div[contains(@class, 'lastAttribute')]")
                    for elem in cellular_elements:
                        price = extract_price_from_text(elem.text)
                        if price:
                            cellular_price = price
                            break
        except:
            pass
    
    return wifi_price, cellular_price

def get_price(driver):
    """Get the price from the page using multiple methods"""
    # Method 1: Look for price in main product area
    try:
        price_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'RM') and contains(@class, 'price')]")
        if price_elements:
            for element in price_elements:
                price = extract_price_from_text(element.text)
                if price:
                    print(f"Found price in main area: RM{price}")
                    return price
    except:
        pass
    
    # Method 2: Look for the large price display near the top
    try:
        price_elements = driver.find_elements(By.CSS_SELECTOR, "div.price, span.price, .product-price")
        for element in price_elements:
            price = extract_price_from_text(element.text)
            if price:
                print(f"Found price in price display: RM{price}")
                return price
    except:
        pass
    
    # Method 3: Look for RM followed by price in large text
    try:
        price_pattern = r'RM(\d{1,3}(?:,\d{3})*(?:\.\d+)?)'
        price_elements = driver.find_elements(By.XPATH, f"//span[contains(text(), 'RM')]/parent::div")
        for element in price_elements:
            element_text = element.text
            if "RM" in element_text:
                price = extract_price_from_text(element_text)
                if price:
                    print(f"Found price in text: RM{price}")
                    return price
    except:
        pass
    
    # Method 4: Find large price in the page
    try:
        large_price = driver.execute_script("""
            const elements = document.querySelectorAll('*');
            const priceElements = [];
            elements.forEach(el => {
                if (el.textContent && el.textContent.includes('RM')) {
                    priceElements.push(el.textContent);
                }
            });
            return priceElements;
        """)
        
        if large_price:
            for text in large_price:
                price = extract_price_from_text(text)
                if price:
                    print(f"Found large price: RM{price}")
                    return price
    except:
        pass
    
    return None

def get_device_color(driver):
    """Extract color information from the page"""
    try:
        # Method 1: Look for "Color:" label
        color_sections = driver.find_elements(By.XPATH, "//div[contains(text(), 'Color:')]/parent::div")
        if color_sections:
            # Get selected color
            selected_colors = driver.find_elements(By.CSS_SELECTOR, "button.active[data-key='color']")
            if selected_colors:
                color_text = selected_colors[0].get_attribute("data-text")
                if color_text:
                    return color_text
            
            # If no selected color found, try to get the first available color
            for section in color_sections:
                color_buttons = section.find_elements(By.TAG_NAME, "button")
                for button in color_buttons:
                    color_text = button.get_attribute("data-text")
                    if color_text:
                        return color_text
        
        # Method 2: Try extracting from title
        title = get_page_title(driver)
        known_colors = ["Gold", "Silver", "Black", "White", "Blue", "Green", "Purple", 
                       "Red", "Gray", "Graphite", "Sierra Blue", "Pacific Blue",
                       "Midnight", "Starlight", "Pink", "Yellow", "Orange", "Monet Purple"]
        
        for color in known_colors:
            if color.lower() in title.lower():
                return color
    except:
        pass
    
    return ""  # Default if not found

def process_tablet_device(driver, device_name, device_type, brand, model, color):
    """Special processing for tablet devices with connectivity options - simplified approach"""
    device_data = []
    
    try:
        # Get storage options
        storage_options = find_storage_options(driver)
        
        # Process each storage option
        for storage_option in storage_options:
            storage_text = storage_option["value"]
            storage_button = storage_option["element"]
            
            # Format capacity display
            if not storage_text:
                capacity_display = ""
            else:
                storage_gb = extract_storage_from_text(storage_text)
                capacity_display = f"{storage_gb}GB"
                if storage_gb == 1024:
                    capacity_display = "1TB"
                elif storage_gb == 2048:
                    capacity_display = "2TB"
            
            # Click on storage button if available
            if storage_button:
                try:
                    print(f"Clicking on storage: {storage_text}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", storage_button)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", storage_button)
                    time.sleep(2)  # Wait for page to update
                except Exception as e:
                    print(f"Error clicking storage button: {e}")
            
            # Get both connectivity prices directly
            wifi_price, cellular_price = get_connectivity_prices(driver)
            
            # Use fallback price if needed
            fallback_price = get_price(driver)
            
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Create WiFi entry if price found
            if wifi_price:
                device_data.append({
                    'Country': 'Malaysia',
                    'Device Type': device_type,
                    'Brand': brand,
                    'Model': model,
                    'Capacity': capacity_display,
                    'Color': color,
                    'Launch RRP': "",
                    'Condition': 'Good',
                    'Value Type': 'Sell-Off',
                    'Currency': 'MYR',
                    'Value': wifi_price,
                    'Source': 'MY_SO_Source2',
                    'Updated on': today,
                    'Updated by': '',
                    'Comments': "WiFi"
                })
                print(f"Extracted: {device_name} - {capacity_display} - WiFi - RM{wifi_price}")
            
            # Create WiFi+Cellular entry if price found
            if cellular_price:
                device_data.append({
                    'Country': 'Malaysia',
                    'Device Type': device_type,
                    'Brand': brand,
                    'Model': model,
                    'Capacity': capacity_display,
                    'Color': color,
                    'Launch RRP': "",
                    'Condition': 'Good',
                    'Value Type': 'Sell-Off',
                    'Currency': 'MYR',
                    'Value': cellular_price,
                    'Source': 'MY_SO_Source2',
                    'Updated on': today,
                    'Updated by': '',
                    'Comments': "WiFi + Cellular"
                })
                print(f"Extracted: {device_name} - {capacity_display} - WiFi + Cellular - RM{cellular_price}")
            
            # If no prices found but we have a fallback, use it (last resort)
            if not wifi_price and not cellular_price and fallback_price:
                device_data.append({
                    'Country': 'Malaysia',
                    'Device Type': device_type,
                    'Brand': brand,
                    'Model': model,
                    'Capacity': capacity_display,
                    'Color': color,
                    'Launch RRP': "",
                    'Condition': 'Good',
                    'Value Type': 'Sell-Off',
                    'Currency': 'MYR',
                    'Value': fallback_price,
                    'Source': 'MY_SO_Source2',
                    'Updated on': today,
                    'Updated by': '',
                    'Comments': ""
                })
                print(f"Extracted: {device_name} - {capacity_display} - RM{fallback_price}")
        
        return device_data
    
    except Exception as e:
        print(f"Error processing tablet device: {e}")
        traceback.print_exc()
        return []

def process_device_listing(driver, url):
    """Process a device listing page"""
    device_data = []
    
    # Skip Mac URLs
    if not should_process_url(url):
        print(f"Skipping Mac device: {url}")
        return device_data
    
    try:
        print(f"Navigating to: {url}")
        try:
            driver.get(url)
            time.sleep(5)  # Wait for page to load
        except TimeoutException:
            print("Page load timed out, but continuing anyway")
            driver.execute_script("window.stop();")  # Stop page loading
        
        # Get device name
        device_name = get_page_title(driver)
        print(f"Processing device: {device_name}")
        
        # Determine device type
        device_type = determine_device_type(device_name)
        
        # Extract brand from device name
        brand = extract_brand_from_device(device_name)
        
        # Extract model name - try from URL first, then from device name
        model_from_url = extract_model_from_url(url)
        if model_from_url:
            model = model_from_url
        else:
            model = device_name.replace("Used ", "")
        
        # Get device color
        color = get_device_color(driver)
        
        # For tablets, process differently to handle connectivity options
        if device_type == "Tablet":
            return process_tablet_device(driver, device_name, device_type, brand, model, color)
        
        # For watches, there's usually no storage
        if device_type == "SmartWatch":
            # Get the price directly
            price = get_price(driver)
            if price:
                # Get current date
                today = datetime.now().strftime("%Y-%m-%d")
                
                device_data.append({
                    'Country': 'Malaysia',
                    'Device Type': device_type,
                    'Brand': brand,
                    'Model': model,
                    'Capacity': '',  # Leave blank for watches
                    'Color': color,
                    'Launch RRP': "",
                    'Condition': 'Good',
                    'Value Type': 'Sell-Off',
                    'Currency': 'MYR',
                    'Value': price,
                    'Source': 'MY_SO_Source2',
                    'Updated on': today,
                    'Updated by': '',
                    'Comments': ''
                })
                print(f"Extracted: {device_name} - RM{price}")
            return device_data
        
        # For regular smartphones
        # Get storage options
        storage_options = find_storage_options(driver)
        
        # Process each storage option
        for storage_option in storage_options:
            storage_text = storage_option["value"]
            storage_button = storage_option["element"]
            storage_price = storage_option.get("price", None)
            
            # If it's empty storage, we'll use a default display
            if not storage_text:
                capacity_display = ""
            else:
                storage_gb = extract_storage_from_text(storage_text)
                capacity_display = f"{storage_gb}GB"
                if storage_gb == 1024:
                    capacity_display = "1TB"
                elif storage_gb == 2048:
                    capacity_display = "2TB"
            
            # Click on storage button if available
            if storage_button:
                try:
                    print(f"Clicking on storage: {storage_text}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", storage_button)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", storage_button)
                    time.sleep(2)  # Wait for page to update
                except Exception as e:
                    print(f"Error clicking storage button: {e}")
            
            # Get price for this storage option
            price = storage_price
            if not price:
                # Try to find price next to the storage option
                try:
                    if storage_button:
                        # Look for price element near the button
                        price_element = storage_button.find_element(By.XPATH, ".//*[contains(text(), 'RM')]")
                        if price_element:
                            extracted_price = extract_price_from_text(price_element.text)
                            if extracted_price:
                                price = extracted_price
                except:
                    pass
                
                # If still no price, get the general price
                if not price:
                    price = get_price(driver)
            
            # Don't add if we couldn't get a price
            if not price:
                print(f"Could not find price for {storage_text}. Skipping.")
                continue
            
            # Get current date
            today = datetime.now().strftime("%Y-%m-%d")
            
            device_data.append({
                'Country': 'Malaysia',
                'Device Type': device_type,
                'Brand': brand,
                'Model': model,
                'Capacity': capacity_display,
                'Color': color,
                'Launch RRP': "",
                'Condition': 'Good',
                'Value Type': 'Sell-Off',
                'Currency': 'MYR',
                'Value': price,
                'Source': 'MY_SO_Source2',
                'Updated on': today,
                'Updated by': '',
                'Comments': ''
            })
            print(f"Extracted: {device_name} - {capacity_display} - RM{price}")
        
        return device_data
    
    except Exception as e:
        print(f"Error processing device: {e}")
        traceback.print_exc()
        return []

def main():
    """Main function to scrape device prices"""
    global df
    max_retries = 3
    
    # Setup driver
    print("Setting up Chrome WebDriver...")
    driver = setup_driver()
    
    try:
        # Navigate to the target page
        print("Navigating to 3cat.my...")
        driver.get("https://3cat.my/#explore_products")
        
        # Wait for page to load
        time.sleep(5)
        
        # Find all product links
        print("Finding product links...")
        product_urls = find_product_links(driver)
        
        # Remove duplicates
        product_urls = list(set(product_urls))
        print(f"Found {len(product_urls)} unique product links")
        
        # Apply device limit from command-line argument
        if args.num_devices > 0:
            if len(product_urls) > args.num_devices:
                print(f"Limiting to first {args.num_devices} devices (of {len(product_urls)}) as specified by -n argument")
                product_urls = product_urls[:args.num_devices]
        
        # Process each device
        for i, product_url in enumerate(product_urls):
            print(f"\nProcessing device {i+1}/{len(product_urls)}")
            print(f"URL: {product_url}")
            
            # Skip Mac URLs
            if not should_process_url(product_url):
                print(f"Skipping Mac device")
                continue
            
            # Process this device with retries
            device_data = []
            retry_count = 0
            success = False
            
            while not success and retry_count < max_retries:
                try:
                    device_data = process_device_listing(driver, product_url)
                    if device_data:  # Consider success only if we got data
                        success = True
                    else:
                        print("No data extracted, considering as failure")
                        retry_count += 1
                except Exception as e:
                    retry_count += 1
                    print(f"Error processing device (attempt {retry_count}/{max_retries}): {e}")
                    
                    if retry_count < max_retries:
                        print("Retrying after a short delay...")
                        time.sleep(5)
                
                # Update Excel file if we got data
                if device_data:
                    new_rows_df = pd.DataFrame(device_data)
                    
                    # Handle empty df warning
                    if not df.empty or not new_rows_df.empty:
                        df = pd.concat([df, new_rows_df], ignore_index=True)
                        # Only drop duplicates if we actually have rows
                        if not df.empty:
                            df.drop_duplicates(subset=['Model', 'Capacity', 'Condition', 'Comments'], keep='last', inplace=True)
                    else:
                        df = new_rows_df
                        
                    df.to_excel(excel_file, index=False)
                    print(f"Updated Excel file with {len(device_data)} new entries")
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
        # Save final data
        try:
            if 'df' in globals() and not df.empty:
                df.to_excel(excel_file, index=False)
                print(f"Final data saved to {excel_file}")
                
                # Print summary
                print("\nData Summary:")
                print(f"Total devices: {df['Model'].nunique()}")
                print(f"Total entries: {len(df)}")
                
                # Summary by device type
                device_type_summary = df['Device Type'].value_counts()
                print("\nDevice Type Summary:")
                for device_type, count in device_type_summary.items():
                    print(f"{device_type}: {count}")
                
                # Summary by brand
                brand_summary = df['Brand'].value_counts()
                print("\nBrand Summary:")
                for brand, count in brand_summary.items():
                    print(f"{brand}: {count}")
        except Exception as e:
            print(f"Error saving final data: {e}")
        
        # Close driver
        try:
            driver.quit()
            print("Driver closed")
        except:
            print("Driver already closed")

if __name__ == "__main__":
    main()