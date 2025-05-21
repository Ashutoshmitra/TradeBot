from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Initialize the WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

try:
    # Navigate to the product page
    url = "https://compasia.co.th/collections/all-smartphones/products/iphone-13-pro-max?variant=43932395831532"
    driver.get(url)

    # Wait for the page to load fully
    wait = WebDriverWait(driver, 20)

    # Function to simulate click using JavaScript
    def simulate_click(element):
        driver.execute_script("arguments[0].click();", element)

    # Function to get the current price
    def get_price():
        try:
            price_element = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "span.price.price--highlight span.money")
            ))
            return price_element.text
        except Exception as e:
            print(f"Error getting price: {e}")
            return "Price not found"

    # Find storage options dynamically
    storage_elements = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "div.pa_ความจุ div.block-swatch-list div.block-swatch input.block-swatch__radio")
    ))
    storage_inputs = [(elem, elem.get_attribute("value")) for elem in storage_elements]

    # Find condition options dynamically
    condition_elements = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "div.pa_เกรด div.block-swatch-list div.block-swatch input.block-swatch__radio")
    ))
    condition_inputs = [(elem, elem.get_attribute("value")) for elem in condition_elements]

    # Store results
    price_results = []

    # Loop through each storage option
    for storage_elem, storage in storage_inputs:
        try:
            # Click storage option
            simulate_click(storage_elem)
            print(f"Clicked storage: {storage}")

            # Loop through each condition option
            for condition_elem, condition in condition_inputs:
                try:
                    # Click condition option
                    simulate_click(condition_elem)
                    print(f"Clicked condition: {condition}")

                    # Wait 1 second for page to stabilize
                    time.sleep(1)

                    # Get the price
                    price = get_price()
                    price_results.append({
                        "storage": storage,
                        "condition": condition,
                        "price": price
                    })
                    print(f"Price for {storage} / {condition}: {price}")
                except Exception as e:
                    print(f"Error clicking condition {condition} for storage {storage}: {e}")
                    price_results.append({
                        "storage": storage,
                        "condition": condition,
                        "price": "Error retrieving price"
                    })
        except Exception as e:
            print(f"Error clicking storage {storage}: {e}")
            price_results.append({
                "storage": storage,
                "condition": "N/A",
                "price": "Error retrieving price"
            })

    # Print all results
    print("\nPrice Results for All Combinations:")
    for result in price_results:
        print(f"Storage: {result['storage']}, Condition: {result['condition']}, Price: {result['price']}")

finally:
    # Close the browser
    driver.quit()