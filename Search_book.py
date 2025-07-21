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
import concurrent.futures

def scrape_search_results(search_url, max_products=0):
    print("Current working directory:", os.getcwd())
    print("Initializing browser and forcing driver update...")

    from selenium.webdriver.chrome.options import Options
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        print(f"🔍 Navigating to search page: {search_url}")
        driver.get(search_url)
        page_html = driver.page_source
        with open("debug_search_page_source.html", "w", encoding="utf-8") as f:
            f.write(page_html)
        print("Full search page HTML written to debug_search_page_source.html")

        soup = BeautifulSoup(page_html, 'html.parser')

        product_urls = []
        for a in soup.select('a.itemname[href]'):
            product_urls.append(a['href'])

        if max_products > 0:
            product_urls = product_urls[:max_products]

        # --- Parallel execution ---
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(get_isbn_and_cover_with_selenium, url): url for url in product_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    detail = future.result()
                    results.append({"Product-URL": url, **detail})
                except Exception as exc:
                    print(f"❌ Error for {url}: {exc}")
                    results.append({"Product-URL": url, "ISBN": "N/A", "Cover-url": "N/A"})

        # Save results to CSV with header: isbn,cover_url,product_url
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"naiin_search_keigo_with_isbn_{timestamp}.csv"
        df = pd.DataFrame(results)
        # Rename columns to match required header
        df = df.rename(columns={"ISBN": "isbn", "Cover-url": "cover_url", "Product-URL": "product_url"})
        df = df[["isbn", "cover_url", "product_url"]]
        df.to_csv(output_filename, index=False, encoding='utf-8-sig')

        print("\n==============================")
        print(f"✅ Successfully saved product details to {output_filename}")
        print("==============================\n")
        print("--- Product Details ---")
        print(df.to_string())

    except Exception as e:
        print(f"❌ An error occurred during scraping: {e}")
        traceback.print_exc()
        print("--- page source on error ---")
        #print(driver.page_source[:1000])
    finally:
        print("Closing browser...")
        driver.quit()

def parse_product_item(item):
    """Extract product details from a .productitem.item BeautifulSoup element."""
    # Title and URL
    title_tag = item.select_one('.item-details .itemname')
    title = title_tag.get_text(strip=True) if title_tag else 'N/A'
    url = title_tag['href'] if title_tag and title_tag.has_attr('href') else 'N/A'

    # Image
    img_tag = item.select_one('.item-img-block img')
    image_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else 'N/A'

    # Category, Publisher, Product ID, Price
    category = item.get('data-cat', 'N/A')
    publisher = item.get('data-pub', 'N/A')
    product_id = item.get('data-id', 'N/A')
    price = item.get('data-price', 'N/A')
    name = item.get('data-name', 'N/A')

    # Discount percent
    discount_tag = item.select_one('.ribbon span.tw-font-semibold')
    discount_percent = discount_tag.get_text(strip=True).replace('%', '') if discount_tag else '0'

    # Sale price and full price
    sale_price_tag = item.select_one('.price-block .sale-price')
    sale_price = sale_price_tag.get_text(strip=True).replace('บาท', '') if sale_price_tag else 'N/A'
    full_price_tag = item.select_one('.price-block .txt-price')
    full_price = full_price_tag.get_text(strip=True).replace('บาท', '') if full_price_tag else 'N/A'

    # Rating
    rating_tag = item.select_one('.vote-scores')
    rating = rating_tag.get_text(strip=True) if rating_tag else 'N/A'

    return {
        "title": title,
        "url": url,
        "image_url": image_url,
        "category": category,
        "publisher": publisher,
        "product_id": product_id,
        "price": price,
        "name": name,
        "discount_percent": discount_percent,
        "sale_price": sale_price,
        "full_price": full_price,
        "rating": rating
    }

def get_isbn_and_cover_with_selenium(product_url):
    """
    Use Selenium to open the product URL and extract ISBN and cover image URL.
    """
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    isbn = "N/A"
    cover_url = "N/A"

    try:
        driver.get(product_url)
        # Wait for the ISBN meta tag to appear
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//meta[@property='book:isbn']"))
        )
        page_html = driver.page_source
        soup = BeautifulSoup(page_html, 'html.parser')

        # Extract ISBN
        meta_isbn = soup.find('meta', attrs={'property': 'book:isbn'})
        if meta_isbn and meta_isbn.has_attr('content'):
            isbn = meta_isbn['content']

        # Extract cover image URL
        meta_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if meta_image and meta_image.has_attr('content'):
            cover_url = meta_image['content']

    except Exception as e:
        print(f"❌ Error extracting ISBN and cover from {product_url}: {e}")
        traceback.print_exc()
    finally:
        driver.quit()

    return {"ISBN": isbn, "Cover-url": cover_url}

# --- Example usage after getting product_urls ---
# results = []
# for url in product_urls:
#     detail = get_isbn_and_cover_with_selenium(url)
#     results.append({"Product URL": url, **detail})
# df = pd.DataFrame(results)
# df.to_csv("naiin_search_keigo_with_isbn.csv", index=False, encoding='utf-8-sig')

if __name__ == "__main__":
    SEARCH_URL = "https://www.naiin.com/search-result?title=โทโฮ"
    # Set max_products to desired number, 0 for all
    scrape_search_results(SEARCH_URL, max_products=0)