import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os
import time
import traceback

def scrape_product_with_selenium(product_url):
    """
    Scrapes a single product page from naiin.com using Selenium
    and forces the correct chromedriver to be installed.
    """
    print("Initializing browser and forcing driver update...")

    # Set Chrome options to help avoid bot detection
    from selenium.webdriver.chrome.options import Options
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    # This line automatically finds your Chrome v138, downloads
    # the matching driver, and tells Selenium to use it.
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    print(f"🔍 Navigating to product page: {product_url}")
    driver.get(product_url)

    try:
        print("Waiting for page content to load...")
        # Wait up to 5 seconds for the meta tag to appear
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//meta[@property='book:isbn']"))
        )
        print("Content loaded. Scraping data...")

        page_html = driver.page_source
        soup = BeautifulSoup(page_html, 'html.parser')

        # Scrape data
        meta_image = soup.find('meta', attrs={'name': 'twitter:image'})
        cover_url = meta_image['content'] if meta_image and meta_image.has_attr('content') else 'N/A'
        if cover_url.startswith('/'):
            cover_url = f"https://www.naiin.com{cover_url}"

        meta_isbn = soup.find('meta', attrs={'property': 'book:isbn'})
        isbn = meta_isbn['content'] if meta_isbn and meta_isbn.has_attr('content') else 'N/A'

        book_data = {
            "ISBN": isbn,
            "Cover-url": cover_url
        }

        # Save to CSV with timestamp to avoid overwrite
        from datetime import datetime
        df = pd.DataFrame([book_data])
        product_id = os.path.basename(urlparse(product_url).path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"naiin_product_{product_id}_{timestamp}.csv"
        df.to_csv(output_filename, index=False, encoding='utf-8-sig')

        print("\n==============================")
        print(f"✅ Successfully saved data to {output_filename}")
        print("==============================\n")
        print("--- Scraped Data ---")
        print(df.to_string())

    except Exception as e:
        print(f"❌ An error occurred during scraping: {e}")
        traceback.print_exc()
        print("--- page source on error ---")
        print(driver.page_source[:1000])
    finally:
        print("Closing browser...")
        driver.quit()

if __name__ == "__main__":
    PRODUCT_URL = "https://www.naiin.com/product/detail/590779"
    scrape_product_with_selenium(PRODUCT_URL)