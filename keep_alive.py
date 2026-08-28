from playwright.sync_api import sync_playwright
import time

URL = "https://learnpeak.streamlit.app/"


def keep_alive():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        print(f"Opening {URL}...")
        page.goto(URL, wait_until="domcontentloaded")

        print(f"Page loaded: {page.title()}")

        # Keep the browser session alive for a short period
        time.sleep(30)

        print("Closing browser...")
        browser.close()

        print("Done.")


if __name__ == "__main__":
    keep_alive()