from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import pandas as pd
import re
import time
import os
import argparse
from datetime import datetime
import traceback

def scrape_compasia_prices(output_excel_path="TH_SO_Source1.xlsx", n_scrape=None, headless=True, delay=2.0):
    """
    Scrapes device prices from CompAsia Thailand website and saves results to a new Excel file
    
    Args:
        output_excel_path (str): Path to the output Excel file
        n_scrape (int, optional): Number of devices to scrape for testing purposes
        headless (bool): Whether to run the browser in headless mode (default: True)
        delay (float): Delay in seconds between actions (default: 2.0, reduce for faster scraping)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Define URLs to scrape
        urls = [
            "https://compasia.co.th/collections/all-smartphones",
            "https://compasia.co.th/collections/tablets"
        ]
        
        # Load existing data if file exists
        if os.path.exists(output_excel_path):
            try:
                existing_df = pd.read_excel(output_excel_path)
                print(f"Loaded existing data from {output_excel_path} with {len(existing_df)} rows")
                results_df = existing_df
            except Exception as e:
                print(f"Error loading existing file: {e}")
                # Create new DataFrame with required columns
                results_df = pd.DataFrame(columns=[
                    "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
                    "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
                    "Source", "Updated on", "Updated by", "Comments"
                ])
        else:
            # Create new DataFrame with required columns
            results_df = pd.DataFrame(columns=[
                "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
                "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
                "Source", "Updated on", "Updated by", "Comments"
            ])
        
        # Default values for certain columns to match Samsung scrape format
        defaults = {
            "Country": "Thailand",
            "Value Type": "Sell-Off",
            "Currency": "THB",
            "Source": "TH_SO_Source1",
            "Updated on": datetime.now().strftime("%Y-%m-%d"),
            "Color": "",  # Intentionally leave color blank as requested
            "Launch RRP": "",
            "Updated by": "",
            "Comments": ""
        }
        
        # Setup Chrome options
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--start-maximized')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-notifications')
        options.add_argument('--enable-javascript')
        options.add_argument('--disk-cache-size=1048576')
        options.add_argument('--media-cache-size=1048576')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Initialize the driver
        driver = webdriver.Chrome(options=options)
        
        # Total devices processed counter
        total_devices_processed = 0
        
        # Function to safely click using JavaScript with retry
        def safe_click(element, max_retries=3):
            for retry in range(max_retries):
                try:
                    driver.execute_script("arguments[0].click();", element)
                    time.sleep(delay)  # Give time for page to update
                    return True
                except Exception as e:
                    print(f"Click error (attempt {retry+1}/{max_retries}): {e}")
                    if retry == max_retries - 1:
                        return False
                    time.sleep(delay)
            return False
        
        # Function to get elements with retry logic
        def get_elements_with_retry(selector, max_retries=3, wait_time=10, is_by_selector=True):
            retries = 0
            while retries < max_retries:
                try:
                    if is_by_selector:
                        elements = WebDriverWait(driver, wait_time).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                        )
                    else:
                        elements = WebDriverWait(driver, wait_time).until(
                            EC.presence_of_all_elements_located(selector)
                        )
                    return elements
                except StaleElementReferenceException:
                    print(f"Stale reference while getting elements, retry {retries+1}")
                    retries += 1
                    time.sleep(delay)
                except Exception as e:
                    print(f"Error getting elements: {e}")
                    retries += 1
                    if retries >= max_retries:
                        return []
                    time.sleep(delay)
            return []
        
        # Function to get the current price with retry
        def get_price_with_retry(max_retries=3):
            retries = 0
            while retries < max_retries:
                try:
                    # First try the standard price selector
                    try:
                        price_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "span.price.price--highlight span.money")
                        ))
                        price_text = price_element.text.strip()
                        price_match = re.search(r'฿\s*([\d,]+(?:\.\d+)?)', price_text)
                        if price_match:
                            return price_match.group(1).replace(',', '')
                    except:
                        # Try alternative selectors
                        selectors = [
                            "span.product-form__price", 
                            ".price__current", 
                            ".price", 
                            "div.price-list span.money",
                            "div.product-form__info-item span.money"
                        ]
                        
                        for selector in selectors:
                            try:
                                alt_price_element = driver.find_element(By.CSS_SELECTOR, selector)
                                price_text = alt_price_element.text.strip()
                                price_match = re.search(r'฿\s*([\d,]+(?:\.\d+)?)', price_text)
                                if price_match:
                                    return price_match.group(1).replace(',', '')
                            except:
                                continue
                        
                        # If we've exhausted all selectors, try extracting price from page source
                        try:
                            page_source = driver.page_source
                            price_match = re.search(r'price":[\s]?"฿\s*([\d,]+(?:\.\d+)?)', page_source)
                            if price_match:
                                return price_match.group(1).replace(',', '')
                        except:
                            pass
                    
                    return "Price not found"
                except StaleElementReferenceException:
                    print(f"Stale reference while getting price, retry {retries+1}")
                    retries += 1
                    time.sleep(delay)
                except Exception as e:
                    print(f"Error getting price: {e}")
                    retries += 1
                    if retries >= max_retries:
                        return "Price not found"
                    time.sleep(delay)
            return "Price not found"
        
        # Function to extract data from product variants when regular approach fails
        def extract_variants_from_select(title, device_type, brand):
            try:
                # Look for the product variant dropdown
                select_elements = driver.find_elements(By.CSS_SELECTOR, "select#product-select-[0-9]+, select[id^='product-select']")
                
                if select_elements:
                    select_element = select_elements[0]
                    options = select_element.find_elements(By.TAG_NAME, "option")
                    print(f"Found {len(options)} variant options in dropdown")
                    
                    for option in options:
                        try:
                            option_text = option.text.strip()
                            # Parse variant details: typically "Color / Storage / Condition - Price"
                            match = re.search(r'(.+?)\s*/\s*(.+?)\s*/\s*(.+?)\s*-\s*฿\s*([\d,]+)', option_text)
                            
                            if match:
                                color = match.group(1).strip()
                                storage = match.group(2).strip()
                                condition = match.group(3).strip()
                                price = match.group(4).replace(',', '')
                                
                                # Map Thai condition text to English
                                condition_english = condition
                                if condition in ["ดีเยี่ยม", "ดี เยี่ยม"]:
                                    condition_english = "Excellent"
                                elif condition == "ดี":
                                    condition_english = "Good"
                                elif condition == "พอใช้":
                                    condition_english = "Fair Enough"
                                
                                print(f"From dropdown - Storage: {storage}, Condition: {condition_english}, Price: {price}")
                                
                                # Add to results
                                add_result_and_save(title, storage, condition_english, price, device_type, brand)
                        except Exception as e:
                            print(f"Error parsing variant option: {e}")
                    
                    return True
                return False
            except Exception as e:
                print(f"Error extracting variants from select: {e}")
                return False
        
        # Function to add a result and save to Excel
        def add_result_and_save(title, storage_value, condition_english, price, device_type, brand):
            nonlocal results_df
            
            if price != "Price not found":
                row_data = defaults.copy()
                row_data.update({
                    "Device Type": device_type,
                    "Brand": brand,
                    "Model": title,
                    "Capacity": storage_value,
                    "Value": price,
                    "Condition": condition_english
                })
                
                # Check if this exact entry already exists
                duplicate = False
                for idx, row in results_df.iterrows():
                    if (row['Model'] == title and 
                        row['Capacity'] == storage_value and 
                        row['Condition'] == condition_english):
                        duplicate = True
                        # Update price if different
                        if str(row['Value']) != str(price):
                            results_df.at[idx, 'Value'] = price
                            results_df.at[idx, 'Updated on'] = datetime.now().strftime("%Y-%m-%d")
                            print(f"Updated price for {title}, {storage_value}, {condition_english}: {price}")
                        break
                
                # Only add if not a duplicate
                if not duplicate:
                    # Append to results DataFrame
                    results_df = pd.concat([results_df, pd.DataFrame([row_data])], ignore_index=True)
                
                # Save to Excel after each price is added
                if not results_df.empty:
                    os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
                    results_df.to_excel(output_excel_path, index=False)
                    print(f"Saved Excel file after adding price for {title}, {storage_value}, {condition_english}: {output_excel_path}")
        
        # Process product function
        def process_product(url, title, device_type):
            try:
                print(f"Processing product: {title}")
                
                # Navigate to product page
                driver.get(url)
                
                # Wait for product page to load
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.pa_product-meta__title, h1.product-meta__title'))
                    )
                except:
                    print("Timeout waiting for product page to load, continuing anyway")
                
                # Get the updated product title
                try:
                    product_title_element = driver.find_element(By.CSS_SELECTOR, 'h1.pa_product-meta__title, h1.product-meta__title')
                    if product_title_element:
                        title = product_title_element.text.strip()
                        print(f"Found product title: {title}")
                except Exception as e:
                    print(f"Error getting product title: {e}, using original title")
                
                # Clean the title
                title = re.sub(r'฿\s*[\d,]+', '', title).strip()
                title = re.sub(r':[^:]*$', '', title).strip()
                
                # Get brand
                brand = ""
                if "iPhone" in title or "iPad" in title:
                    brand = "Apple"
                elif "Galaxy" in title:
                    brand = "Samsung"
                elif "Pixel" in title:
                    brand = "Google"
                
                # Product data collection
                price_results = []
                
                # Try to find storage options
                storage_attempts = 0
                storage_detected = False
                
                while storage_attempts < 3 and not storage_detected:
                    try:
                        # Look for storage option selector first
                        storage_blocks = get_elements_with_retry("div.pa_ความจุ div.block-swatch-list div.block-swatch, div[data-section-type='product'] div.block-swatch-list div.block-swatch")
                        
                        if storage_blocks:
                            storage_detected = True
                            print(f"Found {len(storage_blocks)} storage options")
                            
                            # Process each storage option
                            for storage_idx, storage_block in enumerate(storage_blocks):
                                try:
                                    # Get storage option text (need to get fresh reference)
                                    storage_label = storage_block.find_element(By.CSS_SELECTOR, "label span.block-swatch__item-text")
                                    storage_value = storage_label.text.strip()
                                    print(f"Clicking storage: {storage_value}")
                                    
                                    # Click on storage option
                                    try:
                                        storage_input = storage_block.find_element(By.CSS_SELECTOR, "input.block-swatch__radio")
                                        result = safe_click(storage_input)
                                    except:
                                        # Try clicking the label if input isn't clickable
                                        result = safe_click(storage_label)
                                    
                                    time.sleep(delay)  # Extra wait
                                    
                                    if not result:
                                        continue
                                    
                                    # Get condition options (need fresh references after each storage selection)
                                    condition_blocks = get_elements_with_retry("div.pa_เกรด div.block-swatch-list div.block-swatch, div[data-option-name='เกรด'] div.block-swatch-list div.block-swatch")
                                    
                                    if condition_blocks:
                                        print(f"Found {len(condition_blocks)} condition options")
                                        
                                        # Process each condition option
                                        for condition_idx, condition_block in enumerate(condition_blocks):
                                            try:
                                                # Get condition label text
                                                condition_label = condition_block.find_element(By.CSS_SELECTOR, "label span.block-swatch__item-text")
                                                condition_value = condition_label.text.strip()
                                                print(f"Clicking condition: {condition_value}")
                                                
                                                # Check if condition is out of stock
                                                sold_out_label = condition_block.find_elements(By.CSS_SELECTOR, "p.pa_pdp-sold-out-label")
                                                if sold_out_label and sold_out_label[0].is_displayed():
                                                    print("หมด")  # Out of stock
                                                
                                                # Click on condition option
                                                try:
                                                    condition_input = condition_block.find_element(By.CSS_SELECTOR, "input.block-swatch__radio")
                                                    result = safe_click(condition_input)
                                                except:
                                                    # Try clicking the label if input isn't clickable
                                                    result = safe_click(condition_label)
                                                
                                                time.sleep(delay * 1.5)  # Additional wait time
                                                
                                                if not result:
                                                    continue
                                                
                                                # Get price
                                                price = get_price_with_retry()
                                                
                                                # Map Thai condition text to English
                                                condition_english = condition_value
                                                if condition_value in ["ดีเยี่ยม", "ดี เยี่ยม"]:
                                                    condition_english = "Excellent"
                                                elif condition_value == "ดี":
                                                    condition_english = "Good"
                                                elif condition_value == "พอใช้":
                                                    condition_english = "Fair Enough"
                                                
                                                print(f"Price for {storage_value} / {condition_english}: {price}")
                                                
                                                price_results.append({
                                                    "storage": storage_value,
                                                    "condition": condition_english,
                                                    "price": price
                                                })
                                                
                                                # Save after each successful price retrieval
                                                if price != "Price not found":
                                                    add_result_and_save(title, storage_value, condition_english, price, device_type, brand)
                                                
                                            except StaleElementReferenceException:
                                                print("Stale condition element, skipping")
                                                continue
                                            except Exception as e:
                                                print(f"Error with condition {condition_idx}: {e}")
                                                continue
                                    else:
                                        print("No condition options found")
                                
                                except StaleElementReferenceException:
                                    print(f"Stale storage element for index {storage_idx}, skipping")
                                    continue
                                except Exception as e:
                                    print(f"Error with storage option {storage_idx}: {e}")
                                    continue
                        else:
                            # No storage options found, try extracting from dropdown
                            print("No storage options found via block-swatch, trying product variants dropdown")
                            dropdown_success = extract_variants_from_select(title, device_type, brand)
                            
                            if not dropdown_success:
                                # Try to get a single price
                                print("Attempting to get single price")
                                price = get_price_with_retry()
                                if price != "Price not found":
                                    # Try to extract capacity from title
                                    capacity_match = re.search(r'(\d+)\s*[GT]B', title)
                                    capacity = capacity_match.group(0) if capacity_match else ""
                                    
                                    price_results.append({
                                        "storage": capacity,
                                        "condition": "Unknown",
                                        "price": price
                                    })
                                    
                                    print(f"Added single price: {capacity} Unknown - ฿{price}")
                                    
                                    # Save the result
                                    add_result_and_save(title, capacity, "Unknown", price, device_type, brand)
                            
                            break  # Exit the storage detection loop after alternative approaches
                        
                    except Exception as e:
                        print(f"Error detecting storage options (attempt {storage_attempts+1}): {e}")
                        storage_attempts += 1
                        # Try refreshing the page
                        driver.refresh()
                        time.sleep(delay * 2)
                
                return len(price_results) > 0
                
            except Exception as e:
                print(f"Error processing product {title}: {e}")
                traceback.print_exc()
                return False
        
        # Loop through each URL (smartphones and tablets)
        for url_index, url in enumerate(urls):
            print(f"\nProcessing URL ({url_index+1}/{len(urls)}): {url}")
            
            # Set device type based on URL
            device_type = "SmartPhone" if "smartphone" in url else "Tablet"
            
            try:
                # Navigate to the collection page
                driver.get(url)
                print(f"Navigating to CompAsia {device_type} collection...")
                
                # Wait for page to fully load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
                )
                
                # Process pages until there are no more or until we hit the limit
                current_page = 1
                has_next_page = True
                
                while has_next_page:
                    print(f"Processing page {current_page}...")
                    
                    # Get all product items on the current page
                    product_items = get_elements_with_retry(".product-item")
                    
                    if not product_items:
                        print("No products found on this page")
                        break
                    
                    # If we're testing, limit the number of products
                    if n_scrape is not None:
                        product_items = product_items[:n_scrape]
                        print(f"Testing mode: Only scraping {n_scrape} devices per page")
                    
                    # Store all product URLs and info from this page to process
                    product_info_list = []
                    
                    # Extract basic info and URLs from product cards
                    for item in product_items:
                        try:
                            product_link = item.find_element(By.CSS_SELECTOR, 'a.product-item__title').get_attribute('href')
                            product_title = item.find_element(By.CSS_SELECTOR, 'a.product-item__title').text.strip()
                            
                            product_info = {
                                "url": product_link,
                                "title": product_title,
                                "device_type": device_type
                            }
                            product_info_list.append(product_info)
                            
                        except Exception as e:
                            print(f"Error extracting product info from card: {e}")
                            continue
                    
                    # Process each product detail page
                    for idx, product_info in enumerate(product_info_list):
                        process_product(
                            product_info["url"], 
                            product_info["title"], 
                            product_info["device_type"]
                        )
                        total_devices_processed += 1
                    
                    # Handle pagination
                    try:
                        has_next_page = False
                        next_buttons = driver.find_elements(By.CSS_SELECTOR, '.pagination__next')
                        if next_buttons:
                            next_button = next_buttons[0]
                            if not ("disabled" in next_button.get_attribute("class")):
                                has_next_page = True
                                next_url = next_button.find_element(By.TAG_NAME, 'a').get_attribute('href')
                                if next_url:
                                    print(f"Navigating to next page: {next_url}")
                                    driver.get(next_url)
                                else:
                                    next_page = current_page + 1
                                    next_url = f"{url}?page={next_page}"
                                    print(f"Navigating to constructed next page URL: {next_url}")
                                    driver.get(next_url)
                                
                                WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
                                )
                                current_page += 1
                        
                        if not has_next_page:
                            print("No next page found, reached the end of pagination")
                    
                    except Exception as e:
                        print(f"Error handling pagination: {e}")
                        has_next_page = False
                    
                    if n_scrape is not None:
                        has_next_page = False
                        print("Testing mode: Stopping after one page")
                
            except Exception as e:
                print(f"Error processing URL {url}: {e}")
                continue
        
        # Final save and cleanup
        if not results_df.empty:
            # Convert Value column to numeric
            results_df['Value'] = pd.to_numeric(results_df['Value'], errors='coerce')
            
            # Drop rows with missing essential values
            results_df = results_df.dropna(subset=['Brand', 'Model', 'Value'])
            
            # Ensure proper column order
            column_order = [
                "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
                "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
                "Source", "Updated on", "Updated by", "Comments"
            ]
            results_df = results_df[column_order]
            
            # Final save
            os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
            results_df.to_excel(output_excel_path, index=False)
            print(f"Final results saved to: {output_excel_path}")
        print(f"All pages processed. {total_devices_processed} devices found.")
        return True
        
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
        if 'results_df' in locals() and not results_df.empty:
            os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
            results_df.to_excel(output_excel_path, index=False)
            print(f"Saved partial results to {output_excel_path}")
        return False
    finally:
        try:
            driver.quit()
            print("Browser closed.")
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape CompAsia Thailand device prices')
    parser.add_argument('-n', type=int, help='Number of devices to scrape per page (for testing)', default=None)
    parser.add_argument('-o', '--output', type=str, help='Output Excel file path', default="TH_SO_Source1.xlsx")
    parser.add_argument('--no-headless', action='store_true', help='Disable headless mode (show browser)')
    parser.add_argument('-d', '--delay', type=float, help='Delay between actions (lower = faster but may be less reliable)', default=2.0)
    args = parser.parse_args()
    
    output_excel_path = args.output
    os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
    print(f"Saving output to: {output_excel_path}")
    
    scrape_compasia_prices(
        output_excel_path, 
        n_scrape=args.n, 
        headless=not args.no_headless,
        delay=args.delay
    )
    print("Script completed. Results have been saved to the Excel file.")