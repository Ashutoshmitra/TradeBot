import os
import time
import random
import pandas as pd
from datetime import datetime
import sys
import traceback
import argparse
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Parse command line arguments
parser = argparse.ArgumentParser(description='Scrape device prices from Carousell')
parser.add_argument('-n', '--num_devices', type=int, default=0, 
                    help='Number of devices to scrape. 0 means scrape all devices (default: 0)')
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

# Excel file path
excel_file = os.path.join(output_dir, f'Device_Prices_{datetime.now().strftime("%Y-%m-%d")}.xlsx')

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
    """Create and return an undetected ChromeDriver instance"""
    options = uc.ChromeOptions()
    # Make sure to allow cookies and JavaScript
    options.add_argument('--enable-javascript')
    options.add_argument('--enable-cookies')
    
    # Allow popups
    options.add_argument('--disable-popup-blocking')
    
    # Additional settings to improve reliability
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # Page load strategy
    options.page_load_strategy = 'eager'  # Don't wait for all resources to load
    
    # Create driver with undetected_chromedriver
    driver = uc.Chrome(options=options)
    
    # Set window size
    driver.set_window_size(1280, 900)
    
    # Set page load timeout
    driver.set_page_load_timeout(30)
    
    return driver

def handle_cloudflare_turnstile(driver):
    """Handle Cloudflare Turnstile CAPTCHA - keep the logic that worked before"""
    print("Looking for Cloudflare Turnstile CAPTCHA...")
    
    # First check if there's a Turnstile iframe
    turnstile_found = False
    
    # Look for iframe that contains Cloudflare challenge
    try:
        iframes = driver.find_elements("tag name", "iframe")
        for iframe in iframes:
            try:
                iframe_src = iframe.get_attribute('src')
                if iframe_src and any(term in iframe_src for term in ["cloudflare", "challenges", "turnstile"]):
                    print(f"Found Cloudflare iframe: {iframe_src}")
                    turnstile_found = True
                    
                    # Switch to the iframe
                    driver.switch_to.frame(iframe)
                    
                    # Wait for elements to load
                    time.sleep(2)
                    
                    # Try to find and click the checkbox or any clickable element
                    try:
                        # Try multiple selectors that might contain the checkbox
                        checkbox_found = False
                        selectors = [
                            "input[type='checkbox']",
                            "div[role='checkbox']",
                            "div.checkbox",
                            "span.mark",
                            "div.captcha-checkbox",
                            "div[tabindex='0']"
                        ]
                        
                        for selector in selectors:
                            elements = driver.find_elements("css selector", selector)
                            for element in elements:
                                if element.is_displayed():
                                    print(f"Clicking element with selector: {selector}")
                                    driver.execute_script("arguments[0].click();", element)
                                    checkbox_found = True
                                    time.sleep(3)  # Wait for verification
                                    break
                            
                            if checkbox_found:
                                break
                        
                        # If no specific element found, try clicking in center of iframe
                        if not checkbox_found:
                            print("No specific elements found, clicking center of iframe")
                            driver.execute_script("""
                                document.elementFromPoint(
                                    window.innerWidth / 2, 
                                    window.innerHeight / 2
                                ).click();
                            """)
                            time.sleep(3)
                            
                    except Exception as e:
                        print(f"Error interacting with iframe elements: {e}")
                    
                    # Switch back to main content
                    driver.switch_to.default_content()
                    break
            except Exception as e:
                print(f"Error processing iframe: {e}")
                driver.switch_to.default_content()
    except Exception as e:
        print(f"Error finding iframes: {e}")
    
    # If no Turnstile found, look for other Cloudflare challenges
    if not turnstile_found:
        print("No Turnstile iframe found, checking for other Cloudflare elements")
        
        cloudflare_indicators = [
            "//div[@id='challenge-running']",
            "//div[@id='challenge-form']",
            "//div[contains(@class, 'cf-browser-verification')]",
            "//div[contains(text(), 'Checking your browser')]",
            "//div[contains(text(), 'Please wait')]"
        ]
        
        for xpath in cloudflare_indicators:
            try:
                elements = driver.find_elements("xpath", xpath)
                if elements and any(el.is_displayed() for el in elements):
                    print(f"Found Cloudflare challenge: {xpath}")
                    turnstile_found = True
                    
                    # Just wait for the automated verification to complete
                    print("Waiting for automated verification...")
                    time.sleep(10)
                    break
            except:
                pass
    
    # Give it some extra time if Cloudflare was detected
    if turnstile_found:
        print("Waiting extra time after Cloudflare verification...")
        time.sleep(5)
    
    return turnstile_found

def extract_storage_from_text(text):
    """Extract storage size in GB from text"""
    import re
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
        "Realme", "Asus", "Poco", "Redmi"
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

def determine_ram(device_name):
    """Estimate RAM based on device model"""
    is_apple = any(keyword in device_name for keyword in ["iPhone", "iPad", "Apple"])
    
    if is_apple:
        if "iPhone 15 Pro" in device_name:
            return 8
        elif "iPhone 15" in device_name or "iPhone 14" in device_name:
            return 6
        elif "iPhone 13" in device_name:
            return 6
        elif "iPhone 12" in device_name or "iPhone 11" in device_name:
            return 4
        elif "iPad Pro" in device_name:
            return 8
        else:
            return 4
    else:
        # Try to find RAM in the name
        import re
        ram_match = re.search(r'(\d+)\s*GB\s*RAM', device_name, re.IGNORECASE)
        if ram_match:
            return int(ram_match.group(1))
        
        # Estimate based on known models
        if "Galaxy S21" in device_name or "Galaxy S22" in device_name:
            return 8
        elif "Pixel" in device_name:
            return 8
        else:
            return 6  # Default for modern Android

def check_page_ready(driver, timeout=10):
    """Check if the page has loaded enough to proceed with scraping"""
    try:
        # Wait for the page to stop showing loading indicators
        end_time = time.time() + timeout
        while time.time() < end_time:
            # Check if any content is visible
            try:
                # Look for common content elements
                for selector in ["h1", "div.D_jj", "div.D_bEP", "div.D_agC"]:
                    elements = driver.find_elements("css selector", selector)
                    if elements and any(el.is_displayed() for el in elements):
                        print(f"Found content element: {selector}")
                        return True
            except:
                pass
                
            # Short wait before next check
            time.sleep(1)
        
        # If we get here, check if there's any visible content at all
        body = driver.find_element("tag name", "body")
        if body.text and len(body.text) > 100:  # Arbitrary threshold
            print("Page has text content but no recognized elements")
            return True
            
        print("Page ready check timed out")
        return False
    except Exception as e:
        print(f"Error in page ready check: {e}")
        return False

def safe_find_element(driver, by, value, timeout=5):
    """Safely find an element with timeout"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except Exception as e:
        print(f"Element not found: {by}={value}, error: {e}")
        return None

def click_load_more_button(driver, max_clicks=30):
    """Click the 'Load More' button until it's no longer available or clickable"""
    print("Starting to click 'Load More' button...")
    click_count = 0
    load_more_found = True
    consecutive_no_new_content = 0
    
    # Continue clicking while the button is found and clickable, up to max_clicks
    while load_more_found and click_count < max_clicks:
        # Try to find the Load More button
        load_more_button = None
        try:
            # Try different possible selectors for the Load More button
            selectors = [
                "button.D_k_.D_kV.D_kN.D_kI.D_kZ.D_cEg",  # Exact class from HTML provided
                "button.D_k_:contains('Load more')",  # Class with text
                "button[type='button']:contains('Load more')",  # General button with text
                "//button[contains(text(), 'Load more')]"  # XPath with text
            ]
            
            for selector_type, selector in [
                (By.CSS_SELECTOR, selectors[0]),
                (By.XPATH, selectors[3])
            ]:
                try:
                    # Wait for button with short timeout
                    load_more_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((selector_type, selector))
                    )
                    
                    # Check if button is displayed
                    if load_more_button.is_displayed():
                        print(f"Found 'Load More' button ({click_count + 1})")
                        break
                except:
                    continue
            
            # If button not found via selectors, try JavaScript
            if not load_more_button:
                button_script = """
                    return Array.from(document.querySelectorAll('button')).find(button => 
                        button.textContent.includes('Load more') || 
                        button.innerText.includes('Load more')
                    );
                """
                load_more_button = driver.execute_script(button_script)
                
                if load_more_button:
                    print(f"Found 'Load More' button via JavaScript ({click_count + 1})")
            
            # If button still not found or not displayed, break the loop
            if not load_more_button or not load_more_button.is_displayed():
                print("'Load More' button not found or not displayed")
                load_more_found = False
                break
            
            # Scroll to the button to make sure it's in view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
            time.sleep(0.5)  # Short pause after scrolling
            
            # Record number of link elements before clicking
            links_before = len(driver.find_elements(By.CSS_SELECTOR, "a.D_jh[href*='certified-used-phone'], a[href*='iphone']"))
            
            # Click the button using JavaScript (more reliable)
            driver.execute_script("arguments[0].click();", load_more_button)
            print(f"Clicked 'Load More' button ({click_count + 1})")
            click_count += 1
            
            # Wait for new content to load
            time.sleep(3)  # Wait for AJAX to complete
            
            # Check if new content was loaded
            links_after = len(driver.find_elements(By.CSS_SELECTOR, "a.D_jh[href*='certified-used-phone'], a[href*='iphone']"))
            
            # If no new links were added, we might have reached the end
            if links_after <= links_before:
                print(f"No new links after clicking 'Load More'. Before: {links_before}, After: {links_after}")
                consecutive_no_new_content += 1
                
                # If we've had multiple clicks with no new content, stop clicking
                if consecutive_no_new_content >= 3:
                    print("No new content after 3 consecutive clicks. Stopping.")
                    load_more_found = False
                    break
            else:
                consecutive_no_new_content = 0
                print(f"Added {links_after - links_before} new links after clicking")
            
        except Exception as e:
            print(f"Error with 'Load More' button: {e}")
            load_more_found = False
            break
        
        # Add a short random delay between clicks to avoid rate limiting
        delay = random.uniform(1, 2)
        time.sleep(delay)
    
    if click_count >= max_clicks:
        print(f"Reached maximum number of clicks ({max_clicks})")
    
    print(f"Finished clicking 'Load More' button. Total clicks: {click_count}")
    return click_count

def process_device_listing(driver, url):
    """Process a device listing page directly (without opening a new tab)"""
    device_data = []
    
    try:
        print(f"Navigating to: {url}")
        try:
            driver.get(url)
            # Don't rely on fixed sleep times - use our page ready check
            page_loaded = check_page_ready(driver, timeout=15)
            if not page_loaded:
                print("Warning: Page might not be fully loaded, but continuing anyway")
        except TimeoutException:
            print("Page load timed out, but continuing anyway")
            driver.execute_script("window.stop();")  # Stop page loading
        
        # Check for Cloudflare
        handle_cloudflare_turnstile(driver)
        
        # Get device name - try multiple approaches
        device_name_element = None
        for selector in ["h1.D_jN", "h1.D_jS", "h1", ".D_aMY h1", "[data-testid='listing-title']"]:
            device_name_element = safe_find_element(driver, By.CSS_SELECTOR, selector)
            if device_name_element:
                break
        
        if device_name_element:
            device_name = device_name_element.text.strip()
        else:
            # Last resort: extract device name from URL or title
            device_name = driver.title.split(" - ")[0] if " - " in driver.title else "Unknown Device"
            if device_name == "Unknown Device" and "iphone" in url.lower():
                device_name = "iPhone (Unknown Model)"
        
        print(f"Processing device: {device_name}")
        
        # Extract brand from device name
        brand = extract_brand_from_device(device_name)
        
        # Extract model name
        model = extract_model_from_device(device_name, brand)
        
        # Determine device type
        device_type = "Tablet" if any(keyword in device_name for keyword in ["iPad", "Tab", "Tablet"]) else "Phone"
        
        # Get initial price with improved price detection
        initial_price = None
        for selector in [
            'span.D_jj.D_jk.D_jn.D_jr.D_ju.D_jw.D_aJn.D_jC',  # Regular price format
            'h2.D_aJn.D_jN',  # Discounted price format (the actual price, not crossed out)
            'div.D_abR h2',  # Any h2 within the price container
            'div.D_abR span:not(s)',  # Any non-strikethrough span in price container
            'div[id="FieldSetField-Container-field_product_price"] span',
            '*[data-testid="listing-price"]',
            'span[class*="price"]'
        ]:
            try:
                price_element = safe_find_element(driver, By.CSS_SELECTOR, selector)
                if price_element:
                    price_text = price_element.text.strip()
                    # Make sure the text has numeric content
                    if any(c.isdigit() for c in price_text):
                        try:
                            # Extract numeric price value (handle S$XXX format)
                            price_text = price_text.replace('S$', '').replace(',', '')
                            initial_price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
                            print(f"Found initial price: S${initial_price} using selector: {selector}")
                            break
                        except ValueError:
                            print(f"Could not parse price from text: {price_text}")
            except Exception as e:
                print(f"Error finding price with selector {selector}: {e}")

        # If still no price found, try using JavaScript as a fallback
        if initial_price is None:
            try:
                # JavaScript to find price text in various formats
                price_script = """
                    // Try to find price elements
                    const priceContainers = document.querySelectorAll('.D_abR, [id*="price"]');
                    let priceText = '';
                    
                    for (const container of priceContainers) {
                        // First look for h2 elements (discounted price)
                        const h2s = container.querySelectorAll('h2');
                        if (h2s.length > 0) {
                            for (const h2 of h2s) {
                                if (h2.textContent.includes('$') || h2.textContent.includes('S$')) {
                                    priceText = h2.textContent;
                                    break;
                                }
                            }
                        }
                        
                        // If no h2 with price, look for spans that aren't strikethrough
                        if (!priceText) {
                            const spans = container.querySelectorAll('span:not(s)');
                            for (const span of spans) {
                                if (span.textContent.includes('$') || span.textContent.includes('S$')) {
                                    priceText = span.textContent;
                                    break;
                                }
                            }
                        }
                        
                        if (priceText) break;
                    }
                    
                    return priceText;
                """
                price_text = driver.execute_script(price_script)
                if price_text and any(c.isdigit() for c in price_text):
                    price_text = price_text.replace('S$', '').replace(',', '')
                    initial_price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
                    print(f"Found initial price via JavaScript: S${initial_price}")
            except Exception as e:
                print(f"Error with JavaScript price extraction: {e}")
        
        # Get storage options - targeting the specific buttons
        storage_buttons = []
        storage_container = None
        try:
            # First, try to find the storage container
            for selector in [
                'div[id="FieldSetField-Container-field_storage"] div.D_acn div.D_aco',  # Exact selector from HTML
                'div[id="FieldSetField-Container-field_storage"]',
                'div[data-testid="storage-selector"]',
                '*[id*="storage"]'
            ]:
                storage_container = safe_find_element(driver, By.CSS_SELECTOR, selector)
                if storage_container:
                    print(f"Found storage container with selector: {selector}")
                    break
            
            if storage_container:
                # Find specific buttons with proper attributes
                storage_buttons = storage_container.find_elements(By.CSS_SELECTOR, 'button[aria-pressed]')
                if not storage_buttons:
                    # Try more generic button selector
                    storage_buttons = storage_container.find_elements(By.TAG_NAME, 'button')
                
                print(f"Found {len(storage_buttons)} storage buttons")
            
            # If no buttons found through container, try direct button selectors
            if not storage_buttons:
                for selector in [
                    'button[aria-pressed] span:contains("GB")',
                    'button span:contains("GB")'
                ]:
                    try:
                        # Use JavaScript to find buttons containing GB text
                        buttons_script = f"""
                            return Array.from(document.querySelectorAll('button')).filter(button => 
                                button.textContent.includes('GB') || 
                                button.textContent.includes('TB')
                            );
                        """
                        storage_buttons = driver.execute_script(buttons_script)
                        if storage_buttons:
                            print(f"Found {len(storage_buttons)} storage buttons via JavaScript")
                            break
                    except Exception as e:
                        print(f"Error with JS button selection: {e}")
        except Exception as e:
            print(f"Error finding storage options: {e}")
        
        # If no storage buttons, process the device with current info
        if not storage_buttons:
            print("No storage options found, using default configuration")
            
            # Extract storage from title
            storage_gb = extract_storage_from_text(device_name)
            
            # Use the initial price found earlier
            if initial_price:
                # Get current date
                today = datetime.now().strftime("%Y-%m-%d")
                
                device_data.append({
                    'Country': 'Singapore',
                    'Device Type': device_type,
                    'Brand': brand,
                    'Model': model,
                    'Capacity': f"{storage_gb}GB",
                    'Color': "", 
                    'Launch RRP': "",
                    'Condition': "Unknown",
                    'Value Type': 'Sell-Off',
                    'Currency': 'SGD',
                    'Value': initial_price,
                    'Source': 'SG_SO_Source1',
                    'Updated on': today,
                    'Updated by': '',
                    'Comments': ''
                })
                print(f"Extracted: {device_name} - {storage_gb}GB - Unknown condition - S${initial_price}")
            else:
                print("Could not find price. Skipping device.")
        
        # Process each storage option
        for i, storage_button in enumerate(storage_buttons):
            try:
                # Get storage text
                try:
                    # Try to find span inside button
                    span_elements = storage_button.find_elements(By.TAG_NAME, "span")
                    if span_elements:
                        storage_text = span_elements[0].text.strip()
                    else:
                        storage_text = storage_button.text.strip()
                except:
                    storage_text = storage_button.text.strip()
                
                print(f"Storage option {i+1}: {storage_text}")
                storage_gb = extract_storage_from_text(storage_text)
                
                # Record currently selected storage button
                currently_selected_storage = None
                try:
                    # Find button with aria-pressed="true" or class D_nK
                    selected_buttons = storage_container.find_elements(By.CSS_SELECTOR, 'button[aria-pressed="true"], button.D_nK')
                    if selected_buttons:
                        for btn in selected_buttons:
                            try:
                                spans = btn.find_elements(By.TAG_NAME, "span")
                                if spans:
                                    currently_selected_storage = spans[0].text.strip()
                                else:
                                    currently_selected_storage = btn.text.strip()
                                break
                            except:
                                pass
                except:
                    currently_selected_storage = None
                
                if currently_selected_storage:
                    print(f"Currently selected storage: {currently_selected_storage}")
                
                # Click on storage using JavaScript (more reliable)
                try:
                    # First, make sure the button is visible by scrolling to it
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", storage_button)
                    time.sleep(0.5)  # Short pause after scrolling
                    
                    # Click using JavaScript
                    driver.execute_script("arguments[0].click();", storage_button)
                    print(f"Clicked on storage: {storage_text}")
                    # Wait a short time for page to update, but not too long
                    time.sleep(2)
                except Exception as e:
                    print(f"Error clicking storage button: {e}")
                    continue
                
                # Check if storage value actually changed
                new_storage_text = None
                try:
                    # Try to find the now-selected button
                    selected_buttons = storage_container.find_elements(By.CSS_SELECTOR, 'button[aria-pressed="true"], button.D_nK')
                    if selected_buttons:
                        spans = selected_buttons[0].find_elements(By.TAG_NAME, "span")
                        if spans:
                            new_storage_text = spans[0].text.strip()
                        else:
                            new_storage_text = selected_buttons[0].text.strip()
                        
                        print(f"Now selected storage: {new_storage_text}")
                        
                        # If storage didn't change to what we clicked, it means this option isn't actually available
                        if new_storage_text != storage_text:
                            print(f"Warning: Storage didn't change to {storage_text} after clicking, it's now {new_storage_text}. This suggests the option is inactive.")
                            # Update the storage_gb value to match what's actually selected
                            storage_gb = extract_storage_from_text(new_storage_text)
                except Exception as e:
                    print(f"Error checking current storage selection: {e}")
                
                # Get condition options - targeting the specific buttons
                condition_buttons = []
                condition_container = None
                try:
                    # First, try to find the condition container
                    for selector in [
                        'div[id="FieldSetField-Container-field_layered_condition"] div.D_acn div.D_aco',  # Exact selector from HTML
                        'div[id="FieldSetField-Container-field_layered_condition"]',
                        'div[data-testid="condition-selector"]',
                        '*[id*="condition"]'
                    ]:
                        condition_container = safe_find_element(driver, By.CSS_SELECTOR, selector)
                        if condition_container:
                            print(f"Found condition container with selector: {selector}")
                            break
                    
                    if condition_container:
                        # Find all condition buttons
                        all_condition_buttons = condition_container.find_elements(By.CSS_SELECTOR, 'button')
                        
                        # Avoid help button by filtering
                        condition_buttons = [btn for btn in all_condition_buttons if "help" not in btn.get_attribute("class").lower()]
                        print(f"Found {len(condition_buttons)} condition buttons after filtering")
                        
                        # Find currently selected condition button (will be used to compare later)
                        selected_condition_button = None
                        selected_condition_text = "Unknown"
                        try:
                            selected_buttons = condition_container.find_elements(By.CSS_SELECTOR, 'button[aria-pressed="true"], button.D_nK')
                            if selected_buttons:
                                selected_condition_button = selected_buttons[0]
                                spans = selected_condition_button.find_elements(By.TAG_NAME, "span")
                                if spans:
                                    selected_condition_text = spans[0].text.strip()
                                else:
                                    selected_condition_text = selected_condition_button.text.strip()
                                print(f"Currently selected condition: {selected_condition_text}")
                        except Exception as e:
                            print(f"Error finding selected condition: {e}")
                    
                except Exception as e:
                    print(f"Error finding condition options: {e}")
                
                # If no condition buttons, get current price for this storage
                if not condition_buttons:
                    try:
                        # Get updated price after storage selection with improved price detection
                        price = None
                        for selector in [
                            'span.D_jj.D_jk.D_jn.D_jr.D_ju.D_jw.D_aJn.D_jC',  # Regular price format
                            'h2.D_aJn.D_jN',  # Discounted price format (the actual price, not crossed out)
                            'div.D_abR h2',  # Any h2 within the price container
                            'div.D_abR span:not(s)',  # Any non-strikethrough span in price container
                            'div[id="FieldSetField-Container-field_product_price"] span',
                            '*[data-testid="listing-price"]',
                            'span[class*="price"]'
                        ]:
                            try:
                                price_element = safe_find_element(driver, By.CSS_SELECTOR, selector)
                                if price_element:
                                    price_text = price_element.text.strip()
                                    # Make sure the text has numeric content
                                    if any(c.isdigit() for c in price_text):
                                        try:
                                            # Extract numeric price value (handle S$XXX format)
                                            price_text = price_text.replace('S$', '').replace(',', '')
                                            price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
                                            print(f"Found price: S${price} for storage {storage_text} using selector: {selector}")
                                            break
                                        except ValueError:
                                            continue
                            except Exception as e:
                                print(f"Error finding price with selector {selector}: {e}")

                        # If still no price found, try using JavaScript as a fallback
                        if price is None:
                            try:
                                # JavaScript to find price text in various formats
                                price_script = """
                                    // Try to find price elements
                                    const priceContainers = document.querySelectorAll('.D_abR, [id*="price"]');
                                    let priceText = '';
                                    
                                    for (const container of priceContainers) {
                                        // First look for h2 elements (discounted price)
                                        const h2s = container.querySelectorAll('h2');
                                        if (h2s.length > 0) {
                                            for (const h2 of h2s) {
                                                if (h2.textContent.includes('$') || h2.textContent.includes('S$')) {
                                                    priceText = h2.textContent;
                                                    break;
                                                }
                                            }
                                        }
                                        
                                        // If no h2 with price, look for spans that aren't strikethrough
                                        if (!priceText) {
                                            const spans = container.querySelectorAll('span:not(s)');
                                            for (const span of spans) {
                                                if (span.textContent.includes('$') || span.textContent.includes('S$')) {
                                                    priceText = span.textContent;
                                                    break;
                                                }
                                            }
                                        }
                                        
                                        if (priceText) break;
                                    }
                                    
                                    return priceText;
                                """
                                price_text = driver.execute_script(price_script)
                                if price_text and any(c.isdigit() for c in price_text):
                                    price_text = price_text.replace('S$', '').replace(',', '')
                                    price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
                                    print(f"Found price via JavaScript: S${price} for storage {storage_text}")
                            except Exception as e:
                                print(f"Error with JavaScript price extraction: {e}")
                        
                        if price:
                            # Get current date
                            today = datetime.now().strftime("%Y-%m-%d")
                            
                            device_data.append({
                                'Country': 'Singapore',
                                'Device Type': device_type,
                                'Brand': brand,
                                'Model': model,
                                'Capacity': f"{storage_gb}GB",
                                'Color': "",
                                'Launch RRP': "",
                                'Condition': "Unknown",
                                'Value Type': 'Sell-Off',
                                'Currency': 'SGD',
                                'Value': price,
                                'Source': 'SG_SO_Source1',
                                'Updated on': today,
                                'Updated by': '',
                                'Comments': ''
                            })
                            print(f"Extracted: {device_name} - {storage_gb}GB - Unknown condition - S${price}")
                    except Exception as e:
                        print(f"Could not extract price for storage {storage_text}: {e}")
                
                # Process each condition
                for j, condition_button in enumerate(condition_buttons):
                    try:
                        # Get condition text
                        try:
                            # Try to find span inside button
                            span_elements = condition_button.find_elements(By.TAG_NAME, "span")
                            if span_elements:
                                condition_text = span_elements[0].text.strip()
                            else:
                                condition_text = condition_button.text.strip()
                        except:
                            condition_text = condition_button.text.strip()
                        
                        if not condition_text:
                            condition_text = "Unknown"
                        
                        print(f"Condition option {j+1}: {condition_text}")
                        
                        # Skip if it looks like a help button
                        if condition_text == "" or "?" in condition_text or len(condition_text) <= 1:
                            print(f"Skipping button that appears to be a help button: '{condition_text}'")
                            continue
                        
                        # Check if this button is currently active
                        try:
                            if condition_button.get_attribute("aria-pressed") == "true" or "D_nK" in condition_button.get_attribute("class"):
                                is_active = True
                                print(f"Condition '{condition_text}' is already selected")
                            else:
                                is_active = False
                        except:
                            is_active = False
                        
                        # Click on condition using JavaScript
                        try:
                            # First, make sure the button is visible by scrolling to it
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", condition_button)
                            time.sleep(0.5)  # Short pause after scrolling
                            
                            # Click using JavaScript
                            driver.execute_script("arguments[0].click();", condition_button)
                            print(f"Clicked on condition: {condition_text}")
                            time.sleep(2)  # Short wait for page to update
                        except Exception as e:
                            print(f"Error clicking condition button: {e}")
                            continue
                        
                        # Check if condition actually changed after clicking
                        try:
                            # Find the now-selected condition button
                            selected_buttons = condition_container.find_elements(By.CSS_SELECTOR, 'button[aria-pressed="true"], button.D_nK')
                            if selected_buttons:
                                currently_selected_button = selected_buttons[0]
                                
                                # Get the condition text of the currently selected button
                                spans = currently_selected_button.find_elements(By.TAG_NAME, "span")
                                if spans:
                                    current_condition_text = spans[0].text.strip()
                                else:
                                    current_condition_text = currently_selected_button.text.strip()
                                
                                print(f"Now selected condition: {current_condition_text}")
                                
                                # If condition didn't change to what we clicked, it means this option isn't valid for this storage
                                if current_condition_text != condition_text:
                                    print(f"Warning: Condition didn't change to {condition_text} after clicking, it's now {current_condition_text}. This suggests the combination is inactive.")
                                    # Use the actual condition that we ended up with
                                    condition_text = current_condition_text
                        except Exception as e:
                            print(f"Error checking current condition selection: {e}")
                        
                        # Get price after condition selection with improved price detection
                        price = None
                        for selector in [
                            'span.D_jj.D_jk.D_jn.D_jr.D_ju.D_jw.D_aJn.D_jC',  # Regular price format
                            'h2.D_aJn.D_jN',  # Discounted price format (the actual price, not crossed out)
                            'div.D_abR h2',  # Any h2 within the price container
                            'div.D_abR span:not(s)',  # Any non-strikethrough span in price container
                            'div[id="FieldSetField-Container-field_product_price"] span',
                            '*[data-testid="listing-price"]',
                            'span[class*="price"]'
                        ]:
                            try:
                                price_element = safe_find_element(driver, By.CSS_SELECTOR, selector)
                                if price_element:
                                    price_text = price_element.text.strip()
                                    # Make sure the text has numeric content
                                    if any(c.isdigit() for c in price_text):
                                        try:
                                            # Extract numeric price value (handle S$XXX format)
                                            price_text = price_text.replace('S$', '').replace(',', '')
                                            price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
                                            print(f"Found price: S${price} for condition {condition_text} using selector: {selector}")
                                            break
                                        except ValueError:
                                            continue
                            except Exception as e:
                                print(f"Error finding price with selector {selector}: {e}")

                        # If still no price found, try using JavaScript as a fallback
                        if price is None:
                            try:
                                # JavaScript to find price text in various formats
                                price_script = """
                                    // Try to find price elements
                                    const priceContainers = document.querySelectorAll('.D_abR, [id*="price"]');
                                    let priceText = '';
                                    
                                    for (const container of priceContainers) {
                                        // First look for h2 elements (discounted price)
                                        const h2s = container.querySelectorAll('h2');
                                        if (h2s.length > 0) {
                                            for (const h2 of h2s) {
                                                if (h2.textContent.includes('$') || h2.textContent.includes('S$')) {
                                                    priceText = h2.textContent;
                                                    break;
                                                }
                                            }
                                        }
                                        
                                        // If no h2 with price, look for spans that aren't strikethrough
                                        if (!priceText) {
                                            const spans = container.querySelectorAll('span:not(s)');
                                            for (const span of spans) {
                                                if (span.textContent.includes('$') || span.textContent.includes('S$')) {
                                                    priceText = span.textContent;
                                                    break;
                                                }
                                            }
                                        }
                                        
                                        if (priceText) break;
                                    }
                                    
                                    return priceText;
                                """
                                price_text = driver.execute_script(price_script)
                                if price_text and any(c.isdigit() for c in price_text):
                                    price_text = price_text.replace('S$', '').replace(',', '')
                                    price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
                                    print(f"Found price via JavaScript: S${price} for condition {condition_text}")
                            except Exception as e:
                                print(f"Error with JavaScript price extraction: {e}")
                        
                        if price:
                            # Get current date
                            today = datetime.now().strftime("%Y-%m-%d")
                            
                            # Map Carousell condition text to CompAsia format
                            # Typical Carousell: "Brand new", "Like new", "Lightly used", "Well used"
                            # Typical CompAsia: "Brand New", "Excellent", "Good", "Fair"
                            mapped_condition = condition_text
                            condition_lower = condition_text.lower()
                            
                            if "brand" in condition_lower:
                                mapped_condition = "Brand New"
                            elif "like new" in condition_lower:
                                mapped_condition = "Excellent"
                            elif "lightly" in condition_lower:
                                mapped_condition = "Good"
                            elif "well" in condition_lower:
                                mapped_condition = "Fair"
                            
                            # Check if this is a duplicate entry
                            is_duplicate = False
                            for entry in device_data:
                                if (entry['Capacity'] == f"{storage_gb}GB" and 
                                    entry['Condition'] == mapped_condition):
                                    is_duplicate = True
                                    break
                            
                            if not is_duplicate:
                                device_data.append({
                                    'Country': 'Singapore',
                                    'Device Type': device_type,
                                    'Brand': brand,
                                    'Model': model,
                                    'Capacity': f"{storage_gb}GB",
                                    'Color': "",
                                    'Launch RRP': "",
                                    'Condition': mapped_condition,
                                    'Value Type': 'Sell-Off',
                                    'Currency': 'SGD',
                                    'Value': price,
                                    'Source': 'SG_SO_Source1',
                                    'Updated on': today,
                                    'Updated by': '',
                                    'Comments': ''
                                })
                                print(f"Extracted: {device_name} - {storage_gb}GB - {mapped_condition} - S${price}")
                            else:
                                print(f"Skipping duplicate entry: {storage_gb}GB - {mapped_condition}")
                        else:
                            print(f"Could not find price for condition {condition_text}")
                    
                    except Exception as e:
                        print(f"Error processing condition: {e}")
            
            except Exception as e:
                print(f"Error processing storage: {e}")
        
        return device_data
    
    except Exception as e:
        print(f"Error processing device: {e}")
        traceback.print_exc()
        return []

def find_device_links(driver):
    """Find device links on the page"""
    card_urls = []
    max_wait = 15  # Maximum wait time in seconds
    
    # Wait for content to load - dynamic check
    start_time = time.time()
    while time.time() - start_time < max_wait:
        # Check if any device listings are visible
        has_content = False
        for selector in [".D_bEP", ".D_agC", "a[href*='certified-used-phone']", "a[href*='iphone']"]:
            try:
                elements = driver.find_elements("css selector", selector)
                if elements and any(el.is_displayed() for el in elements):
                    has_content = True
                    break
            except:
                pass
        
        if has_content:
            print("Found visible content on page")
            break
            
        # Check if there's any indication of an error or empty results
        try:
            body_text = driver.find_element("tag name", "body").text
            if "no results" in body_text.lower() or "not found" in body_text.lower():
                print("Found 'no results' message on page")
                break
        except:
            pass
            
        print("Waiting for content to load...")
        time.sleep(2)
    
    # First, try to find links to certified phone listings
    valid_links = []
    try:
        # Try to find direct links to certified phones
        certified_links = driver.find_elements(By.CSS_SELECTOR, "a.D_jh[href*='certified-used-phone']")
        print(f"Found {len(certified_links)} certified phone links")
        
        for link in certified_links:
            try:
                href = link.get_attribute("href")
                if href and "certified-used-phone" in href and href not in valid_links:
                    # Check if the link looks like a product page rather than a search page
                    if "-P" in href and "viewing_mode=0" in href:
                        valid_links.append(href)
            except:
                continue
    except Exception as e:
        print(f"Error finding certified links: {e}")
    
    # If no valid links found, try looking for device cards
    if not valid_links:
        try:
            # Try to find device cards, which are typically in div.D_bEP or div.D_agC
            card_containers = []
            for selector in ["div.D_bEP", "div.D_agC", "div.D_chM"]:
                containers = driver.find_elements(By.CSS_SELECTOR, selector)
                if containers:
                    card_containers.extend(containers)
                    print(f"Found {len(containers)} containers with selector {selector}")
            
            # Process each container to find the link
            for container in card_containers:
                try:
                    # Find link inside the container
                    links = container.find_elements(By.CSS_SELECTOR, "a.D_jh, a[href*='certified-used-phone']")
                    for link in links:
                        href = link.get_attribute("href")
                        if href and href.startswith("http") and href not in valid_links:
                            # Make sure it's a product page, not a category page
                            if "certified-used-phone" in href and "-P" in href:
                                valid_links.append(href)
                except:
                    continue
        except Exception as e:
            print(f"Error finding device cards: {e}")
    
    # If still no links, try a more targeted approach
    if not valid_links:
        try:
            # Use JavaScript to find all suitable links
            links_script = """
                return Array.from(document.querySelectorAll('a')).filter(link => {
                    const href = link.getAttribute('href');
                    return href && 
                           href.includes('certified-used-phone') && 
                           href.includes('-P') &&
                           !href.includes('/search/');
                }).map(link => link.getAttribute('href'));
            """
            js_links = driver.execute_script(links_script)
            for href in js_links:
                if href not in valid_links:
                    valid_links.append(href)
            
            print(f"Found {len(js_links)} links via JavaScript")
        except Exception as e:
            print(f"Error with JavaScript link finding: {e}")
    
    # Now we have a list of valid links
    print(f"Found {len(valid_links)} valid device links")
    return valid_links

def main():
    """Main function to scrape device prices"""
    global df
    max_retries = 3
    
    # Setup driver
    print("Setting up undetected ChromeDriver...")
    driver = setup_driver()
    
    try:
        # Visit Carousell directly
        print("Visiting Carousell main page...")
        try:
            driver.get("https://www.carousell.sg/")
            time.sleep(5)  # Give it some time to load
        except TimeoutException:
            print("Main page load timed out, but continuing anyway")
            driver.execute_script("window.stop();")  # Stop page loading
        
        # Handle Cloudflare if present
        handle_cloudflare_turnstile(driver)
        
        # Now navigate to the target page
        print("Navigating to certified mobiles page...")
        try:
            driver.get("https://www.carousell.sg/smart_render/?type=market-landing-page&name=ap-certified-mobiles")
            
            # Wait for page to load enough to proceed
            wait_time = 0
            max_wait = 20  # seconds
            step = 2  # check every 2 seconds
            
            while wait_time < max_wait:
                try:
                    # Check if any content is visible
                    if check_page_ready(driver, timeout=2):
                        print("Page content found, continuing")
                        break
                except:
                    pass
                
                wait_time += step
                print(f"Waiting for page content... ({wait_time}/{max_wait}s)")
                time.sleep(step)
            
            # If we hit max wait time, force continue anyway
            if wait_time >= max_wait:
                print("Page load wait time exceeded, continuing anyway")
                driver.execute_script("window.stop();")  # Stop loading
        except TimeoutException:
            print("Certified mobiles page load timed out, but continuing anyway")
            driver.execute_script("window.stop();")  # Stop page loading
        
        # Handle Cloudflare again if needed
        handle_cloudflare_turnstile(driver)
        
        # Click Load More button until it's no longer available
        print("Clicking 'Load More' button to get all listings...")
        click_load_more_button(driver)
        
        # Try to find device links
        print("Looking for device links...")
        card_urls = find_device_links(driver)
        
        # If no links found, try alternative URLs
        if not card_urls:
            print("No device links found. Trying alternative pages...")
            alt_urls = [
                "https://www.carousell.sg/marketplace/certified-used-iphone/",
                "https://www.carousell.sg/certified-used-phones/",
                "https://www.carousell.sg/smartphones/certified/",
                "https://www.carousell.sg/categories/mobilesphones-229/"
            ]
            
            for url in alt_urls:
                print(f"Trying: {url}")
                try:
                    driver.get(url)
                    
                    # Wait for content with short timeout
                    wait_time = 0
                    max_wait = 15  # seconds
                    step = 3  # check every 3 seconds
                    
                    while wait_time < max_wait:
                        # Check if any content is visible
                        try:
                            if check_page_ready(driver, timeout=2):
                                print("Page content found, continuing")
                                break
                        except:
                            pass
                        
                        wait_time += step
                        print(f"Waiting for page content... ({wait_time}/{max_wait}s)")
                        time.sleep(step)
                    
                    # If we hit max wait time, force continue anyway
                    if wait_time >= max_wait:
                        print("Page load wait time exceeded, continuing anyway")
                        driver.execute_script("window.stop();")  # Stop loading
                except TimeoutException:
                    print(f"Page load timed out for {url}, continuing anyway")
                    driver.execute_script("window.stop();")  # Stop page loading
                
                # Handle Cloudflare if needed
                handle_cloudflare_turnstile(driver)
                
                # Click Load More button until it's no longer available
                print(f"Clicking 'Load More' button on {url}...")
                click_load_more_button(driver)
                
                new_urls = find_device_links(driver)
                if new_urls:
                    card_urls.extend(new_urls)
                    print(f"Found {len(new_urls)} links from {url}")
                    break
        
        # Remove duplicates
        card_urls = list(set(card_urls))
        print(f"Found {len(card_urls)} unique device links")
        
        # Apply device limit from command-line argument
        if args.num_devices > 0:
            if len(card_urls) > args.num_devices:
                print(f"Limiting to first {args.num_devices} devices (of {len(card_urls)}) as specified by -n argument")
                card_urls = card_urls[:args.num_devices]
        
        # Process each device
        for i, card_url in enumerate(card_urls):
            print(f"\nProcessing device {i+1}/{len(card_urls)}")
            print(f"URL: {card_url}")
            
            # Process this device with retries
            device_data = []
            retry_count = 0
            success = False
            
            while not success and retry_count < max_retries:
                try:
                    device_data = process_device_listing(driver, card_url)
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
                        
                        # Check if we need to recreate the driver
                        try:
                            # Simple check to see if driver is responsive
                            current_url = driver.current_url
                        except:
                            print("Driver is not responding, recreating...")
                            try:
                                driver.quit()
                            except:
                                pass
                            
                            driver = setup_driver()
                            time.sleep(3)
                
                # Update Excel file if we got data
                if device_data:
                    new_rows_df = pd.DataFrame(device_data)
                    df = pd.concat([df, new_rows_df], ignore_index=True)
                    df.drop_duplicates(subset=['Model', 'Capacity', 'Condition'], keep='last', inplace=True)
                    df.to_excel(excel_file, index=False)
                    print(f"Updated Excel file with {len(device_data)} new entries")
                else:
                    print("No data extracted for this device after all retries")
                
                # Save progress after each device
                df.to_excel(excel_file, index=False)
                print(f"Saved progress to {excel_file}")
                
                # Add random delay between processing (but make it shorter)
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