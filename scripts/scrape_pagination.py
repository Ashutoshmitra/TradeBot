from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def scrape_all_pages():
    base_url = "https://compasia.sg/collections/all-smartphones"
    
    # Set up Chrome options
    chrome_options = Options()
    # chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    # Initialize WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        current_page = 1
        driver.get(base_url)
        print(f"Scraping page {current_page}: {base_url}")

        while True:
            # Wait for pagination to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "pagination"))
            )

            # Here you can add code to scrape page content
            # For example, find all products:
            # products = driver.find_elements(By.CLASS_NAME, 'product-item')
            # for product in products:
            #     title = product.find_element(By.CLASS_NAME, 'product-item__title').text
            #     print(title)

            # Check for next page button
            try:
                next_button = driver.find_element(By.CLASS_NAME, "pagination__next")
                if not next_button.is_enabled():
                    print("No next page found, stopping.")
                    break
                
                # Click next button
                next_button.click()
                current_page += 1
                print(f"Scraping page {current_page}")
                
                # Wait for page to load
                time.sleep(2)  # Add delay to ensure page loads
                
            except:
                print("No next page found or error occurred, stopping.")
                break

        print(f"Finished scraping {current_page} pages.")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_all_pages()