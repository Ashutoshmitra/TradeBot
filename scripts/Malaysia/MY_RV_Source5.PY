from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
import pandas as pd
import os
import argparse
from datetime import datetime

def setup_driver(headless=True):
    """Set up the Chrome WebDriver with appropriate options for better performance."""
    chrome_options = webdriver.ChromeOptions()
    
    # Only enable headless mode if specified
    if headless:
        chrome_options.add_argument("--headless=new")
    
    # Core performance options
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--start-maximized")
    
    # Anti-automation detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # User agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36")
    
    # Use page load strategy eager to speed up page loading
    chrome_options.page_load_strategy = 'eager'
    
    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)
    
    # Set page load timeout
    driver.set_page_load_timeout(60)
    
    # Anti-detection JavaScript
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def scrape_trade_in_prices(output_excel_path="MY_RV_Source5.xlsx", n_scrape=None, headless=True, delay=1):
    """
    Scrapes device trade-in prices from Maxis website and saves results to an Excel file
    
    Args:
        output_excel_path (str): Path to the output Excel file
        n_scrape (int, optional): Number of devices to scrape per brand for testing
        headless (bool): Whether to run the browser in headless mode
        delay (float): Delay in seconds between actions
        
    Returns:
        bool: True if successful, False otherwise
    """
    URL = 'https://www.maxis.com.my/en/devices/trade-in/'

    # Use the setup_driver function
    driver = setup_driver(headless=headless)
    
    # Wait times
    ignored_exceptions = (NoSuchElementException, StaleElementReferenceException)
    wait = WebDriverWait(driver, 15, 0.5, ignored_exceptions=ignored_exceptions)
    short_wait = WebDriverWait(driver, 5, 0.5, ignored_exceptions=ignored_exceptions)
    
    # Create DataFrame for results
    results_df = pd.DataFrame(columns=[
        "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
        "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
        "Source", "Updated on", "Updated by", "Comments"
    ])
    
    # Default values
    defaults = {
        "Country": "Malaysia",
        "Value Type": "Trade-In",
        "Source": "MY_RV_Source5",
        "Updated on": datetime.now().strftime("%Y-%m-%d"),
        "Color": "",
        "Launch RRP": "",
        "Updated by": "",
        "Comments": "",
        "Capacity": ""
    }
    
    # Function to use JavaScript to click elements
    def js_click(element):
        driver.execute_script("arguments[0].click();", element)
    
    # Function to check radio buttons with JavaScript
    def js_check_radio(element_id):
        try:
            script = f"""
            var radio = document.getElementById('{element_id}');
            if(radio) {{
                radio.checked = true;
                var event = new Event('change', {{ 'bubbles': true }});
                radio.dispatchEvent(event);
                return true;
            }}
            return false;
            """
            return driver.execute_script(script)
        except Exception as e:
            print(f"[ERROR] Failed to check radio {element_id}: {e}")
            return False
    
    # Function to check checkboxes with JavaScript
    def js_check_checkbox(element_id, check=True):
        try:
            script = f"""
            var checkbox = document.getElementById('{element_id}');
            if(checkbox) {{
                checkbox.checked = {str(check).lower()};
                var event = new Event('change', {{ 'bubbles': true }});
                checkbox.dispatchEvent(event);
                return true;
            }}
            return false;
            """
            return driver.execute_script(script)
        except Exception as e:
            print(f"[ERROR] Failed to check checkbox {element_id}: {e}")
            return False
    
    # Function to use try different methods to select a screen condition radio button
    def select_screen_condition(condition):
        print(f"[INFO] Selecting screen condition: {condition}")
        
        # Screen condition mapping
        condition_id_map = {
            "Flawless": "CPTS01", 
            "2-3 Scratches": "CPTS02",
            "Cracked": "CPTS04"  # Note: "Heavy Scratches" is CPTS03
        }
        
        element_id = condition_id_map.get(condition)
        if not element_id:
            print(f"[ERROR] Unknown condition: {condition}")
            return False
        
        # Method 1: Direct JavaScript method
        result = js_check_radio(element_id)
        if result:
            print(f"[INFO] Selected {condition} using direct JS method")
            return True
        
        # Method 2: Find by name and value
        try:
            script = f"""
            var radios = document.getElementsByName('CPTS');
            for (var i = 0; i < radios.length; i++) {{
                if (radios[i].value === '{element_id}') {{
                    radios[i].checked = true;
                    var event = new Event('change', {{ 'bubbles': true }});
                    radios[i].dispatchEvent(event);
                    return true;
                }}
            }}
            return false;
            """
            result = driver.execute_script(script)
            if result:
                print(f"[INFO] Selected {condition} using name/value JS method")
                return True
        except Exception as e:
            print(f"[ERROR] Failed to select using name/value: {e}")
        
        # Method 3: Find by label text
        try:
            script = f"""
            var paragraphs = document.getElementsByTagName('p');
            for (var i = 0; i < paragraphs.length; i++) {{
                if (paragraphs[i].textContent.trim() === '{condition}') {{
                    var parent = paragraphs[i].parentNode;
                    while (parent && !parent.querySelector('input[type="radio"]')) {{
                        parent = parent.parentNode;
                    }}
                    if (parent) {{
                        var radio = parent.querySelector('input[type="radio"]');
                        radio.checked = true;
                        var event = new Event('change', {{ 'bubbles': true }});
                        radio.dispatchEvent(event);
                        return true;
                    }}
                }}
            }}
            return false;
            """
            result = driver.execute_script(script)
            if result:
                print(f"[INFO] Selected {condition} using text content method")
                return True
        except Exception as e:
            print(f"[ERROR] Failed to select using text content: {e}")
        
        print(f"[ERROR] All methods to select {condition} failed")
        return False
    
    # Function to fill form for a specific screen condition
    def fill_form(screen_condition):
        print(f"[INFO] Filling form with screen condition: {screen_condition}")
        
        # Wait for form to load
        time.sleep(1)
        
        # 1. Select the screen condition
        if not select_screen_condition(screen_condition):
            print(f"[ERROR] Failed to select screen condition: {screen_condition}")
            return False
        
        # Wait between selections
        time.sleep(1)
        
        # 2. Always select Body Flawless
        try:
            body_flawless_checked = js_check_radio("CPBP01")
            print(f"[INFO] Body Flawless checked: {body_flawless_checked}")
        except Exception as e:
            print(f"[ERROR] Failed to select body condition: {e}")
            return False
        
        # Wait between selections
        time.sleep(1)
        
        # 3. Set Q7 (Issues) to "None of the above"
        try:
            # Uncheck all other issue checkboxes
            issue_checkboxes = ["CBAT", "CTON", "CBRK", "CLIQ", "CMIS"]
            for issue_id in issue_checkboxes:
                js_check_checkbox(issue_id, False)
            
            # Check "None of the above"
            none_checked = js_check_checkbox("CISS", True)
            print(f"[INFO] 'None of the above' checked: {none_checked}")
        except Exception as e:
            print(f"[ERROR] Failed to set issues: {e}")
            return False
        
        # Wait after form completion
        time.sleep(1)
        return True
    
    # Function to extract price from the result page
    def extract_price():
        try:
            # Wait for price element to be visible
            time.sleep(1)
            
            price_selectors = [
                ".valuationAmount", 
                "h1.mb-0.green1", 
                "h1.green1", 
                ".price",
                "h1"
            ]
            
            price_text = None
            for selector in price_selectors:
                try:
                    price_element = short_wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, selector)))
                    price_text = price_element.text.strip()
                    print(f"[INFO] Found price using selector '{selector}': {price_text}")
                    break
                except:
                    continue
            
            if not price_text:
                # Try JavaScript as last resort
                price_text = driver.execute_script("""
                    var elements = document.querySelectorAll('*');
                    for(var i=0; i<elements.length; i++) {
                        var text = elements[i].textContent.trim();
                        if(text.match(/RM\\s*\\d+/)) {
                            return text;
                        }
                    }
                    return "";
                """)
                
            # Extract numeric value if found
            if price_text and "RM" in price_text:
                price_match = re.search(r'RM\s*(\d+(?:\.\d+)?)', price_text)
                if price_match:
                    return price_match.group(1)
            
            return ""
            
        except Exception as e:
            print(f"[ERROR] Failed to extract price: {e}")
            return ""
    
    # Function to submit the form and get price
    def submit_form_and_get_price():
        try:
            # Find and click the submit button
            submit_button = driver.find_element(By.CSS_SELECTOR, "input.btn.btn-success[type='submit']")
            js_click(submit_button)
            print("[INFO] Submit button clicked")
            
            # Wait for page to load
            time.sleep(1)  # Increased wait time
            
            # Extract price
            price = extract_price()
            return price
        except Exception as e:
            print(f"[ERROR] Form submission failed: {e}")
            return ""
    
    # Main execution loop
    try:
        # Define screen conditions to test for each model
        screen_conditions = ["Flawless", "2-3 Scratches", "Cracked"]
        
        # Define brands to scrape
        brands = ['Apple', 'Samsung']  # Only these two brands
        
        # Process each combination of brand, model, and condition
        for brand in brands:
            print(f"\n[INFO] Processing brand: {brand}")
            
            # Initial wait before starting
            time.sleep(1)
            
            # First load the page
            driver.get(URL)
            
            # Wait for page to load
            time.sleep(1)
            
            # Find and switch to iframe
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
                print("[INFO] Found iframe, page is ready")
                
                # Wait before switching to iframe
                time.sleep(1)
                
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
                print(f"[INFO] Found {len(iframes)} iframe(s)")
                
                if len(iframes) == 0:
                    print("[ERROR] No iframes found")
                    continue
                
                driver.switch_to.frame(0)
                print("[INFO] Switched to iframe")
                
                # Wait after switching to iframe
                time.sleep(1)
            except Exception as e:
                print(f"[ERROR] Failed to switch to iframe: {e}")
                continue
            
            # Select brand to get models using multiple methods
            try:
                # Wait before brand selection
                time.sleep(1)
                
                select_brand_element = wait.until(EC.presence_of_element_located((By.ID, 'manufacturer')))
                select_brand = Select(select_brand_element)
                
                # Get available brands
                available_brands = []
                for option in select_brand.options:
                    if option.text != "Select One" and option.text.strip() != "":
                        available_brands.append(option.text.strip())
                
                print(f"[INFO] Available brands: {available_brands}")
                
                # Try to find exact match or similar brand name
                brand_match = None
                for available_brand in available_brands:
                    if brand.lower() in available_brand.lower() or available_brand.lower() in brand.lower():
                        brand_match = available_brand
                        break
                
                if brand_match:
                    select_brand.select_by_visible_text(brand_match)
                    print(f"[INFO] Selected brand: {brand_match}")
                else:
                    # Try by index as fallback
                    index = 1 if brand == 'Apple' else 2  # Index 1 for Apple, 2 for Samsung
                    select_brand.select_by_index(index)
                    print(f"[INFO] Selected brand by index: {index}")
                
                # Wait for models to load
                time.sleep(1)
                
                # Get all models
                select_model_element = wait.until(EC.presence_of_element_located((By.ID, 'tinProduct')))
                select_model = Select(select_model_element)
                
                models = []
                for option in select_model.options:
                    if option.text != "Select One" and option.text.strip() != "":
                        models.append(option.text)
                
                print(f"[INFO] Found {len(models)} models for {brand}")
                
                # Limit models if testing
                if n_scrape is not None:
                    models = models[:n_scrape]
                    print(f"[INFO] Limited to {len(models)} models for testing")
                else:
                    # Limit to 5 models by default for stability
                    models = models[:5]
                    print(f"[INFO] Limited to 5 models for stability")
                
            except Exception as e:
                print(f"[ERROR] Failed to get models for {brand}: {e}")
                continue
            
            # Process each model
            for model in models:
                print(f"\n[INFO] Processing model: {model}")
                
                # Process each screen condition for this model
                for condition in screen_conditions:
                    print(f"\n[INFO] Processing condition: {condition}")
                    
                    # Start fresh for each condition to avoid state issues
                    driver.get(URL)
                    
                    # Wait for page to load
                    time.sleep(1)
                    
                    # Switch to iframe
                    try:
                        wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
                        time.sleep(1)  # Wait before switching
                        
                        iframes = driver.find_elements(By.TAG_NAME, "iframe")
                        if len(iframes) > 0:
                            driver.switch_to.frame(0)
                            time.sleep(1)  # Wait after switching
                        else:
                            print("[ERROR] No iframes found, cannot proceed")
                            continue
                    except Exception as e:
                        print(f"[ERROR] Failed to switch to iframe: {e}")
                        continue
                    
                    # Select brand
                    try:
                        # Wait before selection
                        time.sleep(1)
                        
                        select_brand_element = wait.until(EC.presence_of_element_located((By.ID, 'manufacturer')))
                        select_brand = Select(select_brand_element)
                        
                        # Try to select by text first
                        try:
                            # Find the closest match
                            brand_match = None
                            for option in select_brand.options:
                                if brand.lower() in option.text.lower() or option.text.lower() in brand.lower():
                                    brand_match = option.text
                                    break
                            
                            if brand_match:
                                select_brand.select_by_visible_text(brand_match)
                            else:
                                # Fallback to index
                                index = 1 if brand == 'Apple' else 2
                                select_brand.select_by_index(index)
                        except:
                            # Fallback to index
                            index = 1 if brand == 'Apple' else 2
                            select_brand.select_by_index(index)
                        
                        # Wait for models to load
                        time.sleep(1)
                        
                        # Select model
                        select_model_element = wait.until(EC.presence_of_element_located((By.ID, 'tinProduct')))
                        select_model = Select(select_model_element)
                        select_model.select_by_visible_text(model)
                        print(f"[INFO] Selected model: {model}")
                        
                        # Wait before clicking Next
                        time.sleep(1)
                        
                        # Find and click Next button
                        next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.btn-success")))
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                        time.sleep(1)
                        js_click(next_button)
                        print("[INFO] Clicked Next button")
                        
                        # Wait for form page to load
                        time.sleep(1)
                        
                        # Fill form with the current condition
                        if fill_form(condition):
                            # Submit form and get price
                            price = submit_form_and_get_price()
                            
                            # Create a result entry
                            result = defaults.copy()
                            result.update({
                                "Device Type": "Smartphone" if "iPhone" in model or "Galaxy" in model else "Tablet",
                                "Brand": brand,
                                "Model": model,
                                "Condition": condition,
                                "Currency": "MYR",
                                "Value": price
                            })
                            
                            # Extract capacity if present in model name
                            capacity_match = re.search(r'(\d+\s*(?:GB|TB))', model)
                            if capacity_match:
                                result["Capacity"] = capacity_match.group(1).replace(" ", "")
                            
                            # Add to results DataFrame
                            results_df = pd.concat([results_df, pd.DataFrame([result])], ignore_index=True)
                            print(f"[INFO] Added result: {brand} {model} {condition} - RM{price}")
                            
                        # Save progress
                        if len(results_df) % 1 == 0:  # Save every 1 records
                            try:
                                results_df.to_excel(output_excel_path, index=False)
                                print(f"[INFO] Saved progress to {output_excel_path}")
                            except Exception as save_error:
                                print(f"[WARNING] Could not save progress: {save_error}")
                        else:
                            print(f"[ERROR] Could not fill form for {condition}")
                        
                    except Exception as e:
                        print(f"[ERROR] Failed to process {model} with {condition}: {e}")
                        
                        # Try to recreate browser if needed
                        try:
                            driver.current_url  # Check if browser is still responsive
                        except:
                            print("[WARNING] Browser appears to have crashed, recreating...")
                            driver.quit()
                            driver = setup_driver(headless=headless)
                            wait = WebDriverWait(driver, 15, 0.5, ignored_exceptions=ignored_exceptions)
                            short_wait = WebDriverWait(driver, 5, 0.5, ignored_exceptions=ignored_exceptions)
                            break  # Break to next model
                        
                        continue
    
    except Exception as e:
        print(f"[ERROR] Main process error: {e}")
    
    finally:
        # Save results to Excel
        try:
            if not results_df.empty:
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
                
                results_df.to_excel(output_excel_path, index=False)
                print(f"[INFO] Results saved to {output_excel_path}")
        except Exception as e:
            print(f"[ERROR] Failed to save results: {e}")
        
        # Close the browser
        try:
            driver.quit()
            print("[INFO] Browser closed")
        except:
            print("[WARNING] Browser may have already closed")
        
        return not results_df.empty

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape Maxis Trade-in device prices')
    parser.add_argument('-n', type=int, help='Number of devices to scrape per brand (for testing)', default=None)
    parser.add_argument('-o', '--output', type=str, help='Output Excel file path', default="MY_RV_Source5.xlsx")
    parser.add_argument('--no-headless', action='store_true', help='Disable headless mode (show browser)')
    parser.add_argument('-d', '--delay', type=float, help='Delay between actions (lower = faster)', default=1.0)
    parser.add_argument('--retry', type=int, help='Number of retry attempts', default=2)
    args = parser.parse_args()
    
    output_excel_path = args.output
    
    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
    print(f"Saving output to: {output_excel_path}")
    
    # Add retry mechanism
    success = False
    for attempt in range(args.retry + 1):
        if attempt > 0:
            print(f"\n[INFO] Retry attempt {attempt}/{args.retry}")
            time.sleep(5)  # Wait between retries
        
        try:
            result = scrape_trade_in_prices(
                output_excel_path, 
                n_scrape=args.n, 
                headless=not args.no_headless,
                delay=args.delay
            )
            if result:
                success = True
                break
        except Exception as e:
            print(f"[ERROR] Attempt {attempt+1} failed with error: {e}")
            if attempt < args.retry:
                print(f"[INFO] Waiting before next retry...")
                time.sleep(5)  # Wait between retries
    
    if success:
        print("Script completed successfully. Results have been saved to the Excel file.")
    else:
        print("Script failed after all retry attempts.")