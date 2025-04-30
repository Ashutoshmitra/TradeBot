from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
import time
import re

def extract_product_id(url):
    """Extract the unique product ID from a Carousell URL."""
    # Look for patterns like P123456-PV123456-r or similar product identifiers
    match = re.search(r'P\d+-PV\d+-r', url)
    if match:
        return match.group(0)
    return None

def scrape_carousell_smartphones():
    """Scrape Carousell for smartphone listings, handling 'Load more' pagination."""
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # Uncomment the line below to run in headless mode
    # chrome_options.add_argument("--headless")
    
    # Initialize the Chrome driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # Navigate to the webpage
        url = "https://www.carousell.sg/smart_render/?type=market-landing-page&name=ap-certified-mobiles"
        print(f"Navigating to {url}")
        driver.get(url)
        
        # Wait for the page to load
        print("Waiting for page to load...")
        time.sleep(5)
        
        # Set to track unique product IDs
        all_product_ids = set()
        page_num = 1
        
        while True:
            print(f"\n--- Page {page_num} ---")
            
            # Wait for content to load
            time.sleep(3)
            
            # Find all links on the current page
            links = driver.find_elements(By.TAG_NAME, "a")
            
            # Extract smartphone product IDs
            product_ids_on_page = set()
            smartphone_links = []
            
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if href and "/certified-used-phone-l/" in href and "viewing_mode=0" in href:
                        product_id = extract_product_id(href)
                        if product_id:
                            product_ids_on_page.add(product_id)
                            smartphone_links.append(href)
                except Exception:
                    continue
            
            # Find new product IDs not seen before
            new_product_ids = product_ids_on_page - all_product_ids
            all_product_ids.update(new_product_ids)
            
            # Print statistics
            print(f"Total smartphone links on this page: {len(smartphone_links)}")
            print(f"Unique products on this page: {len(product_ids_on_page)}")
            print(f"NEW products on this page: {len(new_product_ids)}")
            print(f"Cumulative unique products found so far: {len(all_product_ids)}")
            
            # Check if there's a "Load more" button
            try:
                print("\nLooking for 'Load more' button...")
                load_more_button = None
                
                # Try to find by CSS selector
                try:
                    load_more_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "div.D_cEm > button.D_le"))
                    )
                except TimeoutException:
                    pass
                
                # Try to find by button text
                if not load_more_button:
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    for button in buttons:
                        try:
                            if "Load more" in button.text:
                                load_more_button = button
                                break
                        except StaleElementReferenceException:
                            continue
                
                if not load_more_button:
                    print("No 'Load more' button found. Reached the end of the listings.")
                    break
                
                print("'Load more' button found. Clicking...")
                driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", load_more_button)
                print("Clicked 'Load more' button")
                
                # Wait for new content to load
                time.sleep(5)
                page_num += 1
                
            except Exception as e:
                print(f"Error while dealing with 'Load more' button: {e}")
                print("Reached the end of the listings or encountered an error.")
                break
        
        # Print final results
        print(f"\n=== Final Results ===")
        print(f"Total number of unique smartphone products found: {len(all_product_ids)}")
            
    except Exception as e:
        print(f"An error occurred: {e}")
        
    finally:
        # Close the browser
        driver.quit()

if __name__ == "__main__":
    print("Starting Carousell smartphone scraper...")
    scrape_carousell_smartphones()
    print("Scraping completed.")