from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import pandas as pd
import re
import time
import os
import argparse
from datetime import datetime


def scrape_trade_in_prices(output_excel_path="Samsung_Trade_In_Values.xlsx", n_scrape=None, headless=True, delay=1):
    """
    Scrapes trade-in prices by company name and saves results to a new Excel file
    
    Args:
        output_excel_path (str): Path to the output Excel file
        n_scrape (int, optional): Number of devices to scrape for testing purposes
        headless (bool): Whether to run the browser in headless mode (default: True)
        delay (float): Delay in seconds between actions (default: 1, reduce for faster scraping)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # List of companies to scrape
        companies = ["Apple", "Samsung", "Google", "Huawei", "Xiaomi", "Oppo", "OnePlus", "Sony", "LG", "Motorola", "Vivo", "Realme", "Honor", "Nubia", "Nothing"]
        
        # Create the results DataFrame with required columns
        results_df = pd.DataFrame(columns=[
            "Country", "Device Type", "Brand", "Model", "Capacity", "Color", 
            "Launch RRP", "Condition", "Value Type", "Currency", "Value", 
            "Source", "Updated on", "Updated by", "Comments"
        ])
        
        # Default values for certain columns
        defaults = {
            "Country": "Singapore",
            "Value Type": "Trade-in",
            "Currency": "SGD",
            "Source": "SG_RV_Source2",
            "Updated on": datetime.now().strftime("%Y-%m-%d"),
            "Color": "",
            "Launch RRP": "",
            "Condition": "",
            "Updated by": "",
            "Comments": ""
        }
        
        # Setup Chrome options
        options = webdriver.ChromeOptions()
        # Only enable headless mode if specified
        if headless:
            options.add_argument('--headless')
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
        
        # Process only a subset of companies if n_scrape is specified
        if n_scrape is not None and n_scrape > 0:
            companies = companies[:n_scrape]
            print(f"Testing mode: Only scraping {n_scrape} companies")
        
        # Counter for all models
        total_models_processed = 0
        
        # Loop through each company
        for company_idx, company in enumerate(companies):
            print(f"\nProcessing company ({company_idx+1}/{len(companies)}): {company}")
            
            try:
                # Start fresh for each company
                driver.get('https://www.samsung.com/sg/trade-in/')
                print(f"Navigating to Samsung trade-in website for {company}...")
                
                # Wait for page to fully load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, 'body'))
                )
                
                # Wait for the search input to be available
                search_input = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '.typeahead.form-control.ng-isolate-scope.tt-input'))
                )
                
                # Click on search input to focus it
                search_input.click()
                time.sleep(delay / 2)  # Reduced delay
                
                # Clear the existing search input
                search_input.clear()
                search_input.send_keys(Keys.CONTROL + "a")
                search_input.send_keys(Keys.DELETE)
                
                # Type the company name all at once rather than character-by-character
                search_input.send_keys(company)
                
                # Wait for the dropdown to appear
                time.sleep(delay)  # Maintain original delay here
                
                try:
                    # Use a single consistent dropdown selector
                    dropdown_selector = '.tt-suggestion.tt-selectable'
                    
                    dropdown_items = WebDriverWait(driver, 3).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, dropdown_selector))
                    )
                    
                    # If no dropdown items found, try once more with additional key press
                    if len(dropdown_items) == 0:
                        print(f"Trying again for {company} with additional input...")
                        search_input.send_keys(Keys.SPACE)
                        search_input.send_keys(Keys.BACKSPACE)
                        time.sleep(delay)
                        
                        dropdown_items = WebDriverWait(driver, 3).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, dropdown_selector))
                        )
                    
                    # If still no items, continue to next company
                    if len(dropdown_items) == 0:
                        print(f"No models found for {company} after multiple attempts")
                        
                        # Take a screenshot for debugging
                        screenshot_path = f"{company}_debug.png"
                        driver.save_screenshot(screenshot_path)
                        print(f"Debug screenshot saved to {screenshot_path}")
                        
                        continue
                    
                    print(f"Found {len(dropdown_items)} models for {company}")
                    
                    # Get text of all dropdown items to process them one by one
                    model_texts = [item.text for item in dropdown_items]
                    
                    # Process each model
                    for model_idx, model_text in enumerate(model_texts):
                        if n_scrape is not None and model_idx >= n_scrape:
                            print(f"Testing mode: Stopping after {n_scrape} models for {company}")
                            break
                            
                        # Start fresh for each model
                        driver.get('https://www.samsung.com/sg/trade-in/')
                        
                        # Wait for the page to load
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, 'body'))
                        )
                        
                        # Find the search input
                        search_input = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, '.typeahead.form-control.ng-isolate-scope.tt-input'))
                        )
                        
                        # Click to focus and clear
                        search_input.click()
                        search_input.clear()
                        search_input.send_keys(Keys.CONTROL + "a")
                        search_input.send_keys(Keys.DELETE)
                        
                        # Type the model text all at once
                        search_input.send_keys(model_text)
                        time.sleep(delay / 2)  # Reduced delay
                            
                        try:
                            # Look for dropdown item
                            dropdown_items = WebDriverWait(driver, 3).until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, dropdown_selector))
                            )
                            
                            if dropdown_items and len(dropdown_items) > 0:
                                dropdown_item = dropdown_items[0]
                                print(f"Processing model ({model_idx+1}/{len(model_texts)}): {model_text}")
                                dropdown_item.click()
                                
                                # Wait for the trade-in price section to load
                                WebDriverWait(driver, 5).until(
                                    EC.visibility_of_element_located((By.ID, 'estTier1'))
                                )
                                
                                # Extract the trade-in price
                                price_element = driver.find_element(By.ID, 'estTier1')
                                price_text = price_element.text
                                
                                # Extract the numeric price using regex that handles commas in the number
                                price_match = re.search(r'\$([\d,]+)', price_text)
                                if price_match:
                                    price = price_match.group(1).replace(',', '')  # Remove commas
                                    print(f"Found trade-in price: ${price_match.group(1)}")
                                    
                                    # Determine if this is a phone or tablet
                                    device_type = "Smartphone"  # Default
                                    if "Tab" in model_text or "Tablet" in model_text or "iPad" in model_text:
                                        device_type = "Tablet"
                                    
                                    # Extract capacity if available
                                    capacity = ""
                                    capacity_match = re.search(r'(\d+)GB', model_text) or re.search(r'(\d+)TB', model_text)
                                    if capacity_match:
                                        capacity = capacity_match.group(0)
                                    
                                    # Create a result entry
                                    result = defaults.copy()
                                    result.update({
                                        "Device Type": device_type,
                                        "Brand": company,
                                        "Model": model_text,
                                        "Capacity": capacity,
                                        "Value": price
                                    })
                                    
                                    # Append to results DataFrame
                                    results_df = pd.concat([results_df, pd.DataFrame([result])], ignore_index=True)
                                    
                                    total_models_processed += 1
                                    
                                else:
                                    print(f"Price not found in element text: {price_text}")
                            else:
                                print(f"Could not find dropdown item for model: {model_text}")
                                
                        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
                            print(f"Error processing model {model_text}: {e}")
                            continue
                        
                except TimeoutException:
                    print(f"No dropdown suggestion for company: {company}")
                    
                    # Take a screenshot for debugging
                    screenshot_path = f"{company}_timeout_debug.png"
                    driver.save_screenshot(screenshot_path)
                    print(f"Debug screenshot saved to {screenshot_path}")
                    
                    continue
                    
            except Exception as e:
                print(f"Error processing company {company}: {e}")
                
                # Take a screenshot for debugging
                try:
                    screenshot_path = f"{company}_error_debug.png"
                    driver.save_screenshot(screenshot_path)
                    print(f"Error screenshot saved to {screenshot_path}")
                except:
                    pass
            
            # Save after each company is processed
            if not results_df.empty:
                # Ensure directory exists
                os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
                results_df.to_excel(output_excel_path, index=False)
                print(f"Progress saved after company {company}: {total_models_processed} models processed so far")
        
        # Final save of all results
        if not results_df.empty:
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
            results_df.to_excel(output_excel_path, index=False)
            
        print(f"All companies processed. {total_models_processed} models found.")
        print(f"Results saved to: {output_excel_path}")
        return True
        
    except Exception as e:
        print(f"An error occurred: {e}")
        # Save any results collected so far
        if 'results_df' in locals() and not results_df.empty:
            # Ensure directory exists
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
    parser = argparse.ArgumentParser(description='Scrape Samsung trade-in values by company')
    parser.add_argument('-n', type=int, help='Number of companies/models to scrape (for testing)', default=None)
    parser.add_argument('-o', '--output', type=str, help='Output Excel file path', default="Samsung_Trade_In_Values.xlsx")
    parser.add_argument('--no-headless', action='store_true', help='Disable headless mode (show browser)')
    parser.add_argument('-d', '--delay', type=float, help='Delay between actions (lower = faster but may be less reliable)', default=0.5)
    args = parser.parse_args()
    
    output_excel_path = args.output
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_excel_path) if os.path.dirname(output_excel_path) else ".", exist_ok=True)
    print(f"Saving output to: {output_excel_path}")
    
    scrape_trade_in_prices(
        output_excel_path, 
        n_scrape=args.n, 
        headless=not args.no_headless,
        delay=args.delay
    )
    print("Script completed. Results have been saved to the Excel file.")