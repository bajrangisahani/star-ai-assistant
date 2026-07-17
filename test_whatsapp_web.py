import time

from selenium.webdriver.common.by import By

from main import create_chrome_driver


def has_logged_in(driver):
    selectors = [
        "//div[@aria-label='Chat list']",
        "//div[@role='grid']",
        "//div[@contenteditable='true']",
        "//div[@role='textbox']",
        "//span[@title]",
        "//header",
    ]

    for selector in selectors:
        if driver.find_elements(By.XPATH, selector):
            return True
    return False


def has_qr_code(driver):
    return bool(driver.find_elements(By.TAG_NAME, "canvas"))


def main():
    driver = create_chrome_driver()
    try:
        driver.get("https://web.whatsapp.com")
        print("[STAR] WhatsApp Web opened.")
        print("[STAR] If QR is visible, scan it from your phone.")

        deadline = time.time() + 120
        logged_in = False

        while time.time() < deadline:
            if has_logged_in(driver):
                logged_in = True
                break

            if has_qr_code(driver):
                print("[STAR] QR/login screen detected. Waiting...")
            else:
                print("[STAR] Waiting for WhatsApp Web to finish loading...")

            time.sleep(5)

        if not logged_in:
            print("[STAR] Login test failed or timed out after 120 seconds.")
            return 1

        print("[STAR] Login detected.")

        textboxes = driver.find_elements(By.XPATH, "//div[@contenteditable='true'] | //div[@role='textbox']")
        print(f"[STAR] Editable boxes found: {len(textboxes)}")

        chats = driver.find_elements(By.XPATH, "//span[@title]")
        names = [safe_text(chat.get_attribute("title")) for chat in chats[:5] if chat.get_attribute("title")]
        if names:
            print("[STAR] Sample chats visible:", ", ".join(names))
        else:
            print("[STAR] Chat list loaded, but no chat titles were readable.")

        print("[STAR] WhatsApp Web basic test passed.")
        return 0
    finally:
        time.sleep(5)
        driver.quit()


def safe_text(value):
    if not value:
        return ""
    return value.encode("ascii", errors="ignore").decode("ascii").strip()


if __name__ == "__main__":
    raise SystemExit(main())
