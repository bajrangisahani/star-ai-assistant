import time
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


def open_whatsapp(driver):
    driver.get("https://web.whatsapp.com")
    time.sleep(8)


def search_chat(driver, name):
    search_boxes = driver.find_elements(By.XPATH, "//div[@contenteditable='true']")
    if not search_boxes:
        return False

    box = search_boxes[0]
    box.click()
    box.send_keys(Keys.CONTROL, "a")
    box.send_keys(name)
    time.sleep(2)
    box.send_keys(Keys.ENTER)
    time.sleep(2)
    return True


def send_message(driver, contact, message):
    open_whatsapp(driver)

    if not search_chat(driver, contact):
        return "WhatsApp search box was not found. Login may be required."

    message_boxes = driver.find_elements(By.XPATH, "//div[@contenteditable='true'][@data-tab]")
    if not message_boxes:
        return "WhatsApp message box was not found."

    box = message_boxes[-1]
    box.click()
    box.send_keys(message)
    box.send_keys(Keys.ENTER)
    return f"WhatsApp message sent to {contact}."


def open_chat(driver, contact):
    open_whatsapp(driver)
    if search_chat(driver, contact):
        return f"Opened WhatsApp chat with {contact}."
    return "WhatsApp search box was not found. Login may be required."


def web_send_url(phone, message):
    clean_phone = "".join(char for char in str(phone) if char.isdigit())
    if not clean_phone:
        return None
    return f"https://wa.me/{clean_phone}?text={quote_plus(message)}"
