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


def scrape_compasia_prices(output_excel_path="MY_SO_Source1.xlsx", n_scrape=None, headless=True, delay=1):
    """
    Scrapes device prices from CompAsia website and saves results to a new Excel file
    
    Args:
        output_excel_path (str): Path to the output Excel file
        n_scrape (int, optional): Number of devices to scrape for testing purposes
        headless (bool): Whether to run the browser in headless mode (default: True)
        delay (float): Delay in seconds between actions (default: 1, reduce for faster scraping)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Define URLs to scrape
        urls = [
            "https://compasia.my/collections/all-smartphones",
            "https://compasia.my/collections/tablets"
        ]
        
        # Create the results DataFrame with required columns to match Samsung scrape format
        results_df = pd.DataFrame(columns=[
            "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
            "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
            "Source", "Updated on", "Updated by", "Comments"
        ])
        
        # Default values for certain columns to match Samsung scrape format
        defaults = {
            "Country": "Malaysia",
            "Value Type": "Sell-Off",
            "Currency": "MYR",
            "Source": "MY_SO_Source1",
            "Updated on": datetime.now().strftime("%Y-%m-%d"),
            "Color": "",
            "Launch RRP": "",
            "Updated by": "",
            "Comments": ""
        }
        
        # Setup Chrome options
        options = webdriver.ChromeOptions()
        # Only enable headless mode if specified
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--start-maximized')
        options.add_argument('--window-size=1920,1080')
        # Add performance options
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-notifications')
        options.add_argument('--enable-javascript')
        # Cache settings
        options.add_argument('--disk-cache-size=1048576')
        options.add_argument('--media-cache-size=1048576')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Initialize the driver
        driver = webdriver.Chrome(options=options)
        
        # Total devices processed counter
        total_devices_processed = 0
        
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
                    product_items = WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.CLASS_NAME, 'product-item'))
                    )
                    
                    # If we're testing, limit the number of products
                    if n_scrape is not None:
                        product_items = product_items[:n_scrape]
                        print(f"Testing mode: Only scraping {n_scrape} devices per page")
                    
                    # Store all product URLs and info from this page to process
                    product_info_list = []
                    
                    # Extract basic info and URLs from product cards
                    for item in product_items:
                        try:
                            # Extract product URL
                            product_link = item.find_element(By.CSS_SELECTOR, 'a.product-item__title').get_attribute('href')
                            
                            # Extract product title
                            product_title = item.find_element(By.CSS_SELECTOR, 'a.product-item__title').text.strip()
                            
                            # Extract brand from product data attribute or tags
                            brand = ""
                            try:
                                # Try to get brand from data-tags attribute
                                data_tags = item.get_attribute('data-tags')
                                if data_tags:
                                    tags = data_tags.split(',')
                                    # First tag is usually the brand
                                    brand = tags[0]
                            except:
                                # If we can't get brand from tags, try to extract from title
                                common_brands = ["Apple", "Samsung", "Google", "Huawei", "Xiaomi", "Oppo", "OnePlus", 
                                               "Sony", "LG", "Motorola", "Vivo", "Realme", "Honor", "Nothing"]
                                for b in common_brands:
                                    if b in product_title:
                                        brand = b
                                        break
                            
                            # Extract capacity from data-tags or title
                            capacity = ""
                            try:
                                data_tags = item.get_attribute('data-tags')
                                if data_tags:
                                    tags = data_tags.split(',')
                                    for tag in tags:
                                        if "GB" in tag or "TB" in tag:
                                            capacity = tag.strip()
                                            break
                            except:
                                # Try to extract capacity from title using regex
                                capacity_match = re.search(r'(\d+)GB', product_title) or re.search(r'(\d+)TB', product_title)
                                if capacity_match:
                                    capacity = capacity_match.group(0)
                            
                            # Get base price if available on the card
                            base_price = ""
                            try:
                                price_element = item.find_element(By.CSS_SELECTOR, 'span.price--highlight')
                                price_text = price_element.text.strip()
                                # Extract numeric price - UPDATED for RM format
                                price_match = re.search(r'RM\s*(\d+)', price_text)
                                if price_match:
                                    base_price = price_match.group(1)
                            except:
                                pass
                            
                            # Add product info to list for processing
                            product_info = {
                                "url": product_link,
                                "title": product_title,
                                "brand": brand,
                                "capacity": capacity,
                                "base_price": base_price,
                                "device_type": device_type
                            }
                            product_info_list.append(product_info)
                            
                        except Exception as e:
                            print(f"Error extracting product info from card: {e}")
                            continue
                    
                    # Process each product detail page
                    for idx, product_info in enumerate(product_info_list):
                        try:
                            # Extract model name from the product title in the card
                            model_name = product_info["title"]
                            print(f"Processing product ({idx+1}/{len(product_info_list)}): {model_name}")
                            
                            # Navigate to product page
                            driver.get(product_info["url"])
                            
                            # Wait for product page to load
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.pa_product-meta__title'))
                            )
                            
                            # Get product title from the detail page (more accurate)
                            try:
                                # Look specifically for the heading with the model name
                                product_title_element = driver.find_element(By.CSS_SELECTOR, 'h1.pa_product-meta__title')
                                if product_title_element:
                                    model_name = product_title_element.text.strip()
                                    print(f"Found product title: {model_name}")
                            except Exception as e:
                                print(f"Error getting product title: {e}, using original title")
                                
                            # Clean the model name (remove any price information)
                            model_name = re.sub(r'RM\s*\d+', '', model_name).strip()
                            
                            # Find capacity options section
                            capacity_option_section = None
                            try:
                                # Look for option blocks that contain capacity
                                option_blocks = driver.find_elements(By.CSS_SELECTOR, 'div.product-form__option')
                                for block in option_blocks:
                                    try:
                                        option_label = block.find_element(By.CSS_SELECTOR, 'span.pa_pdp-option-label')
                                        if option_label.text.strip() == "Capacity":
                                            capacity_option_section = block
                                            break
                                    except:
                                        # If we can't find label, check if block contains capacity text
                                        if "capacity" in block.text.lower():
                                            capacity_option_section = block
                                            break
                            except Exception as e:
                                print(f"Error finding capacity option section: {e}")
                                
                            # Extract all available capacities
                            available_capacities = []
                            try:
                                if capacity_option_section:
                                    capacity_blocks = capacity_option_section.find_elements(By.CSS_SELECTOR, 'div.block-swatch')
                                    for block in capacity_blocks:
                                        try:
                                            capacity_label = block.find_element(By.CSS_SELECTOR, 'span.block-swatch__item-text')
                                            capacity_text = capacity_label.text.strip()
                                            if "GB" in capacity_text or "TB" in capacity_text:
                                                # Extract just the capacity part
                                                capacity_value = re.search(r'(\d+\s*[GT]B)', capacity_text)
                                                if capacity_value:
                                                    capacity = capacity_value.group(1).replace(" ", "")
                                                    if capacity not in available_capacities:
                                                        available_capacities.append(capacity)
                                        except:
                                            pass
                                else:
                                    # Try to find capacity blocks more generally
                                    capacity_blocks = driver.find_elements(By.CSS_SELECTOR, 'div.block-swatch')
                                    for block in capacity_blocks:
                                        try:
                                            block_text = block.text.strip()
                                            if "GB" in block_text or "TB" in block_text:
                                                capacity_value = re.search(r'(\d+\s*[GT]B)', block_text)
                                                if capacity_value:
                                                    capacity = capacity_value.group(1).replace(" ", "")
                                                    if capacity not in available_capacities:
                                                        available_capacities.append(capacity)
                                        except:
                                            pass
                            except Exception as e:
                                print(f"Error extracting capacities: {e}")
                                
                            # If we can't get capacities from the page, use what we got from the card
                            if not available_capacities and product_info["capacity"]:
                                available_capacities = [product_info["capacity"]]
                            
                            # If we didn't get any capacities, use an empty placeholder
                            if not available_capacities:
                                available_capacities = [""]
                                
                            # Process each capacity option
                            all_conditions_data = []
                            
                            for capacity_idx, capacity in enumerate(available_capacities):
                                print(f"Processing capacity: {capacity}")
                                
                                # If we have capacity options, click on this capacity
                                if capacity_option_section and capacity and len(available_capacities) > 1:
                                    try:
                                        capacity_blocks = capacity_option_section.find_elements(By.CSS_SELECTOR, 'div.block-swatch')
                                        for block in capacity_blocks:
                                            try:
                                                if capacity in block.text:
                                                    # Click on this capacity option
                                                    block.find_element(By.TAG_NAME, 'label').click()
                                                    # Wait for page to update
                                                    time.sleep(delay)
                                                    break
                                            except:
                                                pass
                                    except Exception as e:
                                        print(f"Error clicking capacity option: {e}")
                                
                                # Find condition options section
                                condition_option_section = None
                                try:
                                    # Look for option blocks that contain condition/grading
                                    option_blocks = driver.find_elements(By.CSS_SELECTOR, 'div.product-form__option')
                                    for block in option_blocks:
                                        try:
                                            option_label = block.find_element(By.CSS_SELECTOR, 'span.pa_pdp-option-label')
                                            label_text = option_label.text.strip().lower()
                                            if "condition" in label_text or "grading" in label_text or "cosmetic" in label_text:
                                                condition_option_section = block
                                                break
                                        except:
                                            # If we can't find label, check if block contains condition text
                                            block_text = block.text.lower()
                                            if "condition" in block_text or "grading" in block_text or "cosmetic" in block_text:
                                                condition_option_section = block
                                                break
                                except Exception as e:
                                    print(f"Error finding condition option section: {e}")
                                
                                # Extract all available conditions and their prices
                                conditions_data = []
                                try:
                                    if condition_option_section:
                                        condition_blocks = condition_option_section.find_elements(By.CSS_SELECTOR, 'div.block-swatch')
                                        for block in condition_blocks:
                                            try:
                                                block_text = block.text.strip()
                                                condition_text = None
                                                
                                                for condition in ["Excellent", "Good", "Fair"]:
                                                    if condition in block_text:
                                                        condition_text = condition
                                                        break
                                                        
                                                if condition_text:
                                                    price = ""
                                                    # First try to extract price from the cosmetic-grading-price div
                                                    try:
                                                        price_div = block.find_element(By.CSS_SELECTOR, 'div.cosmetic-grading-price')
                                                        price_text = price_div.text.strip()
                                                        # Extract price from RM format
                                                        price_match = re.search(r'RM\s*(\d+)', price_text)
                                                        if price_match:
                                                            price = price_match.group(1)
                                                    except:
                                                        # If specific div not found, try to extract from block text
                                                        price_match = re.search(r'RM\s*(\d+)', block_text)
                                                        if price_match:
                                                            price = price_match.group(1)
                                                    
                                                    # Check if this condition is disabled/sold out
                                                    is_disabled = "disabled" in block.get_attribute("class")
                                                    
                                                    conditions_data.append({
                                                        "condition": condition_text,
                                                        "price": price,
                                                        "capacity": capacity,
                                                        "is_disabled": is_disabled
                                                    })
                                            except Exception as ce:
                                                print(f"Error extracting condition data: {ce}")
                                    else:
                                        # Try to find condition blocks more generally
                                        condition_blocks = driver.find_elements(By.CSS_SELECTOR, 'div.block-swatch')
                                        for block in condition_blocks:
                                            try:
                                                block_text = block.text.strip()
                                                condition_text = None
                                                
                                                for condition in ["Excellent", "Good", "Fair"]:
                                                    if condition in block_text:
                                                        condition_text = condition
                                                        break
                                                        
                                                if condition_text:
                                                    price = ""
                                                    # First try to extract price from the cosmetic-grading-price div
                                                    try:
                                                        price_div = block.find_element(By.CSS_SELECTOR, 'div.cosmetic-grading-price')
                                                        price_text = price_div.text.strip()
                                                        # Extract price from RM format
                                                        price_match = re.search(r'RM\s*(\d+)', price_text)
                                                        if price_match:
                                                            price = price_match.group(1)
                                                    except:
                                                        # If specific div not found, try to extract from block text
                                                        price_match = re.search(r'RM\s*(\d+)', block_text)
                                                        if price_match:
                                                            price = price_match.group(1)
                                                    
                                                    # Check if this condition is disabled/sold out
                                                    is_disabled = "disabled" in block.get_attribute("class")
                                                    
                                                    conditions_data.append({
                                                        "condition": condition_text,
                                                        "price": price,
                                                        "capacity": capacity,
                                                        "is_disabled": is_disabled
                                                    })
                                            except Exception as ce:
                                                print(f"Error extracting condition data: {ce}")
                                except Exception as e:
                                    print(f"Error finding condition blocks: {e}")
                                
                                # If we're processing a specific capacity and got condition data, add it to the list
                                if conditions_data:
                                    all_conditions_data.extend(conditions_data)
                                    
                            # If we didn't get any condition data at all, create a default entry with base price
                            if not all_conditions_data and product_info["base_price"]:
                                all_conditions_data.append({
                                    "condition": "Unknown",
                                    "price": product_info["base_price"],
                                    "capacity": available_capacities[0] if available_capacities else "",
                                    "is_disabled": False
                                })
                                
                            # Create entries for condition data without using colors or other unnecessary fields
                            for condition_data in all_conditions_data:
                                # Create a result entry based on the exact format needed
                                result = defaults.copy()
                                result.update({
                                    "Device Type": product_info["device_type"],
                                    "Brand": product_info["brand"],
                                    "Model": model_name,
                                    "Capacity": condition_data["capacity"],
                                    "Value": condition_data["price"],
                                    "Condition": condition_data["condition"]
                                })
                                
                                # Append to results DataFrame
                                results_df = pd.concat([results_df, pd.DataFrame([result])], ignore_index=True)
                            
                            total_devices_processed += 1
                            
                        except Exception as e:
                            print(f"Error processing product {product_info['title']}: {e}")
                            
                            # Take a screenshot for debugging
                            try:
                                product_name = product_info['title'].replace(' ', '_')[:20]  # Truncate for filename
                                screenshot_path = f"{product_name}_error_debug.png"
                                driver.save_screenshot(screenshot_path)
                                print(f"Error screenshot saved to {screenshot_path}")
                            except:
                                pass
                                
                            continue
                    
                    # First, make sure we're back on the collection page, not a product detail page
                    collection_page_url = url
                    if current_page > 1:
                        collection_page_url = f"{url}?page={current_page}"
                    
                    print(f"Navigating back to collection page: {collection_page_url}")
                    driver.get(collection_page_url)
                    
                    # Wait for page to load
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
                    )
                    
                    # Check if there's a next page
                    try:
                        # Wait for pagination to load
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "pagination"))
                        )
                        
                        # Get the pagination info to see total pages
                        pagination_info = driver.find_element(By.CLASS_NAME, "pagination__page-count").text
                        print(f"Pagination info: {pagination_info}")
                        
                        # Extract current page and total pages
                        page_info_match = re.search(r'Page (\d+) / (\d+)', pagination_info)
                        if page_info_match:
                            current_page_num = int(page_info_match.group(1))
                            total_pages = int(page_info_match.group(2))
                            print(f"Current page: {current_page_num}, Total pages: {total_pages}")
                            
                            # Check if we're on the last page
                            if current_page_num >= total_pages:
                                print(f"Reached the last page ({current_page_num}/{total_pages}). No more pages to process.")
                                has_next_page = False
                            else:
                                # Navigate directly to the next page using URL
                                next_page_num = current_page_num + 1
                                next_page_url = f"{url}?page={next_page_num}"
                                
                                print(f"Navigating to page {next_page_num} using URL: {next_page_url}")
                                driver.get(next_page_url)
                                
                                # Wait for products to load on the new page
                                WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
                                )
                                
                                # Increment page counter
                                current_page = next_page_num
                                print(f"Successfully navigated to page {current_page}")
                        else:
                            # If we can't parse the pagination info, try using the next button as backup
                            try:
                                next_button = driver.find_element(By.CLASS_NAME, "pagination__next")
                                if "disabled" in next_button.get_attribute("class") or not next_button.is_enabled():
                                    print("Next button is disabled, no more pages.")
                                    has_next_page = False
                                else:
                                    # Click next button
                                    print(f"Clicking 'Next' button to navigate to page {current_page + 1}...")
                                    next_button.click()
                                    
                                    # Wait for page to load
                                    time.sleep(delay * 2)
                                    
                                    # Wait for products to load on the new page
                                    WebDriverWait(driver, 10).until(
                                        EC.presence_of_element_located((By.CLASS_NAME, 'product-item'))
                                    )
                                    
                                    # Increment page counter
                                    current_page += 1
                                    print(f"Successfully navigated to page {current_page}")
                            except Exception as e:
                                print(f"No next button found: {e}")
                                has_next_page = False
                    except Exception as e:
                        print(f"Error handling pagination: {e}")
                        
                        # Take a screenshot for debugging
                        try:
                            screenshot_path = f"pagination_error_debug_page_{current_page}.png"
                            driver.save_screenshot(screenshot_path)
                            print(f"Error screenshot saved to {screenshot_path}")
                        except:
                            pass
                            
                        has_next_page = False
                    
                    # If testing mode with n_scrape set, only process one page
                    if n_scrape is not None:
                        has_next_page = False
                        print("Testing mode: Stopping after one page")
                    
                    # Save after each page
                    if not results_df.empty:
                        # Ensure output directory exists
                        os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
                        results_df.to_excel(output_excel_path, index=False)
                        print(f"Progress saved after page {current_page}: {total_devices_processed} devices processed so far")
                
            except Exception as e:
                print(f"Error processing URL {url}: {e}")
                
                # Take a screenshot for debugging
                try:
                    screenshot_path = f"url_{url_index}_error_debug.png"
                    driver.save_screenshot(screenshot_path)
                    print(f"Error screenshot saved to {screenshot_path}")
                except:
                    pass
                
                continue
        
        # Final save of all results
        if not results_df.empty:
            # Clean up the data
            # Convert value column to numeric
            results_df['Value'] = pd.to_numeric(results_df['Value'], errors='coerce')
            
            # Drop rows with missing essential data
            results_df = results_df.dropna(subset=['Brand', 'Model'])
            
            # Ensure proper columns order to match Samsung scrape format
            column_order = [
                "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
                "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
                "Source", "Updated on", "Updated by", "Comments"
            ]
            
            # Reorder columns
            results_df = results_df[column_order]
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
            
            # Save final result
            results_df.to_excel(output_excel_path, index=False)
            
        print(f"All pages processed. {total_devices_processed} devices found.")
        print(f"Results saved to: {output_excel_path}")
        return True
        
    except Exception as e:
        print(f"An error occurred: {e}")
        # Save any results collected so far
        if 'results_df' in locals() and not results_df.empty:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
            results_df.to_excel(output_excel_path, index=False)
            print(f"Saved partial results to {output_excel_path}")
        return False
    finally:
        # Close the browser
        try:
            driver.quit()
            print("Browser closed.")
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape CompAsia device prices')
    parser.add_argument('-n', type=int, help='Number of devices to scrape per page (for testing)', default=None)
    parser.add_argument('-o', '--output', type=str, help='Output Excel file path', default="MY_SO_Source1.xlsx")
    parser.add_argument('--no-headless', action='store_true', help='Disable headless mode (show browser)')
    parser.add_argument('-d', '--delay', type=float, help='Delay between actions (lower = faster but may be less reliable)', default=1.0)
    args = parser.parse_args()
    
    output_excel_path = args.output
    
    # Create the output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
    print(f"Saving output to: {output_excel_path}")
    
    scrape_compasia_prices(
        output_excel_path, 
        n_scrape=args.n, 
        headless=not args.no_headless,
        delay=args.delay
    )
    print("Script completed. Results have been saved to the Excel file.")