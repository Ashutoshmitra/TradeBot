from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import re
import time
import os
import argparse
from datetime import datetime
import traceback

def scrape_compasia_prices(output_excel_path="TH_SO_Source1.xlsx", n_scrape=None, headless=True, delay=2.0):
    """
    Scrapes device prices from CompAsia Thailand website and saves results to Excel file
    
    Args:
        output_excel_path (str): Path to the output Excel file
        n_scrape (int, optional): Number of devices to scrape for testing purposes
        headless (bool): Whether to run the browser in headless mode (default: True)
        delay (float): Delay in seconds between actions (default: 2.0)
        
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
                results_df = pd.DataFrame(columns=[
                    "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
                    "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
                    "Source", "Updated on", "Updated by", "Comments"
                ])
        else:
            results_df = pd.DataFrame(columns=[
                "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
                "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
                "Source", "Updated on", "Updated by", "Comments"
            ])
        
        # Default values for certain columns
        defaults = {
            "Country": "Thailand",
            "Value Type": "Sell-Off",
            "Currency": "THB",
            "Source": "TH_SO_Source1",
            "Updated on": datetime.now().strftime("%Y-%m-%d"),
            "Color": "",  # Intentionally leave color blank
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
        # Add auto-translate to English
        options.add_argument('--translate-target-lang=en')
        options.add_argument('--lang=en')
        options.add_experimental_option("prefs", {
            "translate_whitelists": {"th": "en"},
            "translate": {"enabled": True}
        })
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Initialize the driver
        driver = webdriver.Chrome(options=options)
        
        def force_translate_page():
            """Force translate the page to English using JavaScript"""
            try:
                # Wait a moment for page to load
                time.sleep(2)
                
                # Try to trigger Google Translate
                translate_script = """
                // Try to find and click the translate button if it exists
                var translateButton = document.querySelector('[data-translate-button]') || 
                                    document.querySelector('.translate-button') ||
                                    document.querySelector('[aria-label*="translate"]') ||
                                    document.querySelector('[title*="translate"]');
                
                if (translateButton) {
                    translateButton.click();
                    return 'Translate button clicked';
                }
                
                // Alternative: Try to set the page language attribute
                document.documentElement.lang = 'en';
                document.documentElement.setAttribute('translate', 'yes');
                
                return 'Language attributes set';
                """
                
                result = driver.execute_script(translate_script)
                print(f"Translation attempt: {result}")
                
                # Additional wait for translation to process
                time.sleep(3)
                
            except Exception as e:
                print(f"Translation attempt failed: {e}")
        
        def get_all_product_links():
            """Get all product links from all pages of both collections"""
            all_product_links = []
            
            for url_index, url in enumerate(urls):
                print(f"\nGetting product links from URL ({url_index+1}/{len(urls)}): {url}")
                
                # Set device type based on URL
                device_type = "SmartPhone" if "smartphone" in url else "Tablet"
                
                try:
                    driver.get(url)
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
                    )
                    
                    # Force translate the page
                    force_translate_page()
                    
                    current_page = 1
                    has_next_page = True
                    
                    while has_next_page:
                        print(f"Processing page {current_page} for {device_type}...")
                        
                        # Get all product items on current page
                        product_items = driver.find_elements(By.CSS_SELECTOR, '.product-item')
                        
                        if not product_items:
                            print("No products found on this page")
                            break
                        
                        # Extract product links and titles
                        for item in product_items:
                            try:
                                product_link = item.find_element(By.CSS_SELECTOR, 'a.product-item__title').get_attribute('href')
                                product_title = item.find_element(By.CSS_SELECTOR, 'a.product-item__title').text.strip()
                                
                                all_product_links.append({
                                    "url": product_link,
                                    "title": product_title,
                                    "device_type": device_type
                                })
                                
                            except Exception as e:
                                print(f"Error extracting product info: {e}")
                                continue
                        
                        print(f"Found {len(product_items)} products on page {current_page}")
                        
                        # Handle pagination
                        try:
                            has_next_page = False
                            next_buttons = driver.find_elements(By.CSS_SELECTOR, '.pagination__next')
                            if next_buttons:
                                next_button = next_buttons[0]
                                if "disabled" not in next_button.get_attribute("class"):
                                    # Try to get href directly from the next button or its child elements
                                    next_url = None
                                    
                                    # Method 1: Try to get href from the button itself
                                    try:
                                        next_url = next_button.get_attribute('href')
                                    except:
                                        pass
                                    
                                    # Method 2: Try to find 'a' tag inside the button
                                    if not next_url:
                                        try:
                                            next_link = next_button.find_element(By.TAG_NAME, 'a')
                                            next_url = next_link.get_attribute('href')
                                        except:
                                            pass
                                    
                                    # Method 3: Try CSS selector for link inside pagination
                                    if not next_url:
                                        try:
                                            next_link = driver.find_element(By.CSS_SELECTOR, '.pagination__next a')
                                            next_url = next_link.get_attribute('href')
                                        except:
                                            pass
                                    
                                    # Method 4: Construct next page URL manually
                                    if not next_url:
                                        try:
                                            next_page = current_page + 1
                                            next_url = f"{url}?page={next_page}"
                                            print(f"Constructed next page URL: {next_url}")
                                        except:
                                            pass
                                    
                                    if next_url:
                                        print(f"Navigating to next page: {next_url}")
                                        driver.get(next_url)
                                        
                                        # Wait for products to load on next page
                                        try:
                                            WebDriverWait(driver, 10).until(
                                                EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
                                            )
                                            current_page += 1
                                            has_next_page = True
                                        except TimeoutException:
                                            print("No products found on next page, ending pagination")
                                            has_next_page = False
                                    else:
                                        print("Could not determine next page URL")
                            
                            if not has_next_page:
                                print("No next page found, reached the end of pagination")
                        
                        except Exception as e:
                            print(f"Error handling pagination: {e}")
                            has_next_page = False
                
                except Exception as e:
                    print(f"Error processing URL {url}: {e}")
                    continue
            
            print(f"\nTotal product links collected: {len(all_product_links)}")
            return all_product_links
        
        def extract_brand_from_title(title):
            """Extract brand from product title"""
            title_lower = title.lower()
            if "iphone" in title_lower or "ipad" in title_lower:
                return "Apple"
            elif "galaxy" in title_lower or "samsung" in title_lower:
                return "Samsung"
            elif "pixel" in title_lower:
                return "Google"
            elif "xiaomi" in title_lower or "redmi" in title_lower:
                return "Xiaomi"
            elif "oppo" in title_lower:
                return "OPPO"
            elif "vivo" in title_lower:
                return "Vivo"
            elif "huawei" in title_lower:
                return "Huawei"
            elif "oneplus" in title_lower:
                return "OnePlus"
            else:
                return "Unknown"
        
        def map_condition_to_english(thai_condition):
            """Map Thai condition text to English"""
            condition_mapping = {
                "ดีเยี่ยม": "Excellent",
                "ดี เยี่ยม": "Excellent", 
                "excellent": "Excellent",
                "ดี": "Good",
                "good": "Good",
                "พอใช้": "Fair Enough",
                "fair enough": "Fair Enough"
            }
            return condition_mapping.get(thai_condition.lower(), thai_condition)
        
        def add_result_to_dataframe(title, storage, condition, price, device_type, brand):
            """Add a result to the dataframe and save to Excel"""
            nonlocal results_df
            
            if price and price != "Price not found":
                row_data = defaults.copy()
                row_data.update({
                    "Device Type": device_type,
                    "Brand": brand,
                    "Model": title,
                    "Capacity": storage,
                    "Value": price,
                    "Condition": condition
                    # Color remains empty as per original requirement
                })
                
                # Check if this exact entry already exists (storage + condition only)
                duplicate_mask = (
                    (results_df['Model'] == title) & 
                    (results_df['Capacity'] == storage) & 
                    (results_df['Condition'] == condition)
                    # No color in deduplication - so different colors with same storage+condition will be deduplicated
                )
                
                if duplicate_mask.any():
                    # Update existing entry
                    idx = duplicate_mask.idxmax()
                    if str(results_df.at[idx, 'Value']) != str(price):
                        results_df.at[idx, 'Value'] = price
                        results_df.at[idx, 'Updated on'] = datetime.now().strftime("%Y-%m-%d")
                else:
                    # Add new entry
                    results_df = pd.concat([results_df, pd.DataFrame([row_data])], ignore_index=True)
                
                # Save to Excel after each addition
                try:
                    os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
                    results_df.to_excel(output_excel_path, index=False)
                except Exception as e:
                    print(f"Error saving to Excel: {e}")
        
        def process_single_product(product_info):
            """Process a single product to extract all variant prices"""
            try:
                print(f"\nProcessing: {product_info['title']}")
                
                # Navigate to product page
                driver.get(product_info['url'])
                
                # Force translate the product page
                force_translate_page()
                
                # Wait for page to load
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.pa_product-meta__title, h1.product-meta__title'))
                    )
                except TimeoutException:
                    print("Timeout waiting for product page to load")
                    return False
                
                # Get the actual product title from the page
                try:
                    title_element = driver.find_element(By.CSS_SELECTOR, 'h1.pa_product-meta__title, h1.product-meta__title')
                    title = title_element.text.strip()
                    print(f"Product title: {title}")
                    
                except Exception as e:
                    print(f"Error getting product title: {e}")
                    title = product_info['title']
                
                # Extract brand
                brand = extract_brand_from_title(title)
                device_type = product_info['device_type']
                
                # Look for the product variant dropdown
                try:
                    select_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'select[name="id"]'))
                    )
                    
                    options = select_element.find_elements(By.TAG_NAME, "option")
                    print(f"Found {len(options)} variant options")
                    
                    variants_processed = 0
                    
                    # If option text is empty, try to get text using JavaScript
                    if not options[0].text.strip():
                        print("Using JavaScript method to extract option text...")
                        try:
                            # Get option texts using JavaScript
                            js_script = """
                            var select = arguments[0];
                            var options = [];
                            for (var i = 0; i < select.options.length; i++) {
                                options.push({
                                    text: select.options[i].text || select.options[i].innerHTML,
                                    value: select.options[i].value
                                });
                            }
                            return options;
                            """
                            option_data = driver.execute_script(js_script, select_element)
                            
                            # Process JavaScript-extracted options
                            for opt_data in option_data:
                                try:
                                    option_text = opt_data['text'].strip()
                                    if not option_text or option_text == "":
                                        continue
                                    
                                    # Parse variant details: "Color / Storage / Condition - ฿ Price"
                                    # Example: "Pink / 128GB / ดีเยี่ยม - ฿ 12,500"
                                    match = re.search(r'(.+?)\s*/\s*(.+?)\s*/\s*(.+?)\s*-\s*฿\s*([\d,]+)', option_text)
                                    
                                    if match:
                                        color = match.group(1).strip()
                                        storage = match.group(2).strip()
                                        condition = match.group(3).strip()
                                        price = match.group(4).replace(',', '')
                                        
                                        # Map condition to English
                                        condition_english = map_condition_to_english(condition)
                                        
                                        # Add to results (ignore color, only storage + condition)
                                        add_result_to_dataframe(title, storage, condition_english, price, device_type, brand)
                                        variants_processed += 1
                                    
                                except Exception as e:
                                    print(f"Error processing variant: {e}")
                                    continue
                            
                        except Exception as e:
                            print(f"JavaScript extraction failed: {e}")
                    
                    else:
                        # Original method when option text is available
                        for option in options:
                            try:
                                option_text = option.text.strip()
                                if not option_text or option_text == "":
                                    continue
                                
                                # Parse variant details: "Color / Storage / Condition - ฿ Price"
                                # Example: "Black / 256GB / Excellent - ฿ 15,778"
                                match = re.search(r'(.+?)\s*/\s*(.+?)\s*/\s*(.+?)\s*-\s*฿\s*([\d,]+)', option_text)
                                
                                if match:
                                    color = match.group(1).strip()
                                    storage = match.group(2).strip()
                                    condition = match.group(3).strip()
                                    price = match.group(4).replace(',', '')
                                    
                                    # Map condition to English
                                    condition_english = map_condition_to_english(condition)
                                    
                                    # Add to results (ignore color, only storage + condition)
                                    add_result_to_dataframe(title, storage, condition_english, price, device_type, brand)
                                    variants_processed += 1
                                    
                            except Exception as e:
                                print(f"Error processing option: {e}")
                                continue
                    
                    print(f"Successfully processed {variants_processed} variants for {title}")
                    return variants_processed > 0
                    
                except TimeoutException:
                    print("No product variant dropdown found")
                    
                    # Try to get a single price if no variants
                    try:
                        price_element = driver.find_element(By.CSS_SELECTOR, "span.price.price--highlight")
                        price_text = price_element.text.strip()
                        price_match = re.search(r'฿\s*([\d,]+)', price_text)
                        
                        if price_match:
                            price = price_match.group(1).replace(',', '')
                            
                            # Try to extract capacity from title
                            capacity_match = re.search(r'(\d+)\s*[GT]B', title)
                            capacity = capacity_match.group(0) if capacity_match else ""
                            
                            print(f"Single price found: {capacity} - ฿{price}")
                            add_result_to_dataframe(title, capacity, "Unknown", price, device_type, brand)
                            return True
                    except Exception as e:
                        print(f"Error getting single price: {e}")
                    
                    return False
                
            except Exception as e:
                print(f"Error processing product {product_info['title']}: {e}")
                traceback.print_exc()
                return False
        
        # Main execution
        print("Starting CompAsia Thailand price scraping...")
        
        # Step 1: Get all product links
        all_product_links = get_all_product_links()
        
        if not all_product_links:
            print("No product links found!")
            return False
        
        # Step 2: Limit products if testing
        if n_scrape is not None:
            all_product_links = all_product_links[:n_scrape]
            print(f"Testing mode: Processing only {n_scrape} products")
        
        # Step 3: Process each product
        successful_products = 0
        total_products = len(all_product_links)
        
        for idx, product_info in enumerate(all_product_links, 1):
            print(f"\n--- Processing product {idx}/{total_products} ---")
            
            success = process_single_product(product_info)
            if success:
                successful_products += 1
            
            # Add delay between products
            time.sleep(delay)
        
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
            print(f"\nFinal results saved to: {output_excel_path}")
            print(f"Total products processed: {total_products}")
            print(f"Successful products: {successful_products}")
            print(f"Total price entries: {len(results_df)}")
        
        return True
        
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
        if 'results_df' in locals() and not results_df.empty:
            try:
                os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
                results_df.to_excel(output_excel_path, index=False)
                print(f"Saved partial results to {output_excel_path}")
            except Exception as save_error:
                print(f"Error saving partial results: {save_error}")
        return False
    finally:
        try:
            driver.quit()
            print("Browser closed.")
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape CompAsia Thailand device prices')
    parser.add_argument('-n', type=int, help='Number of devices to scrape (for testing)', default=None)
    parser.add_argument('-o', '--output', type=str, help='Output Excel file path', default="TH_SO_Source1.xlsx")
    parser.add_argument('--no-headless', action='store_true', help='Disable headless mode (show browser)')
    parser.add_argument('-d', '--delay', type=float, help='Delay between actions (lower = faster but may be less reliable)', default=2.0)
    args = parser.parse_args()
    
    output_excel_path = args.output
    os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
    print(f"Saving output to: {output_excel_path}")
    
    success = scrape_compasia_prices(
        output_excel_path, 
        n_scrape=args.n, 
        headless=not args.no_headless,
        delay=args.delay
    )
    
    if success:
        print("Script completed successfully. Results have been saved to the Excel file.")
    else:
        print("Script completed with errors. Check the logs above.")