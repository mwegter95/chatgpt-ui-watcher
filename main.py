from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException
import time
import pyperclip  # For clipboard interactions
import re  # For regex operations
import os  # For file operations
import subprocess  # For code formatting


processed_messages = set()

def process_message(message_element):
    """
    Process a single chat message, including extracting code snippets and executing actions.
    """
    message_id = message_element.get_attribute("data-message-id")
    if message_id not in processed_messages:
        message_text_element = message_element.find_element(By.CSS_SELECTOR, 'div.markdown.prose.w-full.break-words.dark\\:prose-invert.light > p')
        message_text = message_text_element.text

        # Attempt to click the "Copy code" button and extract the code snippet
        code_text = None
        try:
            copy_button = message_element.find_element(By.XPATH, './/button[contains(., "Copy code")]')
            copy_button.click()
            time.sleep(1)  # Adjust the delay if needed
            code_text = pyperclip.paste()
        except NoSuchElementException:
            print("Note: 'Copy code' button not found for message:", message_text)

        # If a code snippet was copied, print it
        if code_text:
            print("Code snippet:", code_text)

        # Now parse and execute any action commands present in the message
        action, data_fields = parse_command(message_text)
        
        if action:
            print(f"Executing action: {action}")
            if action == "ADD_FILE":
                add_file(data_fields)
            elif action == "MODIFY_CODE":
                modify_code(data_fields)
                # Optionally, format the modified code
                format_code(data_fields.get('path'))
            # Handle other actions as needed
        else:
            # This case handles both messages without actions and with code snippets
            print("Message processed without actions:", message_text)
        
        processed_messages.add(message_id)


def wait_for_message_stable(browser, message_element, timeout=10):
    """
    Wait until the message text becomes stable.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Double-check if the message text has changed after a brief wait
            time.sleep(1)  # Wait for 1 second
            current_text = message_element.find_element(By.CSS_SELECTOR, 'div.markdown.prose.w-full.break-words.dark\\:prose-invert.light > p').text
            time.sleep(1)  # Wait for 1 second
            new_text = message_element.find_element(By.CSS_SELECTOR, 'div.markdown.prose.w-full.break-words.dark\\:prose-invert.light > p').text
            if current_text == new_text:
                return True
        except StaleElementReferenceException:
            return False
    return False

def monitor_chat(browser):
    """
    Continuously monitor the chat window for new messages.
    """
    while True:
        try:
            # Wait for message containers to be present
            message_containers = WebDriverWait(browser, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[data-message-author-role="assistant"]')))
            
            # Process each message
            for container in message_containers:
                try:
                    if wait_for_message_stable(browser, container):
                        process_message(container)
                except StaleElementReferenceException:
                    # Skip if the element is no longer attached to the DOM
                    continue
        except TimeoutException:
            print("Timed out waiting for message containers.")
        except Exception as e:
            print("An error occurred while monitoring chat:", e)
        
        time.sleep(5)  # Add a delay between iterations to avoid continuous repetition

def parse_command(message):
    action_pattern = r"\[ACTION\]\s*(\w+)"
    data_pattern = r"\[DATA\](.*)"
    
    action_match = re.search(action_pattern, message)
    data_match = re.search(data_pattern, message)
    
    data_fields = {}
    
    if action_match and data_match:
        data_string = data_match.group(1).strip()
        for field in data_string.split(';'):
            key, value = field.split('=', 1)
            data_fields[key.strip()] = value.strip()
            
    return action_match.group(1) if action_match else None, data_fields

def add_file(data):
    # Implementation from previous discussions
    ...

def modify_code(data):
    # Enhanced implementation from previous discussions
    ...

def format_code(file_path):
    # Formatting code using black or prettier
    ...


def main():
    # Initialize WebDriver with remote debugging port
    options = webdriver.ChromeOptions()
    options.debugger_address = "localhost:9333"  # Adjust the port if needed
    browser = webdriver.Chrome(options=options)
    
    try:
        # Navigate to the ChatGPT page
        browser.get("https://chat.openai.com/c/f7fc8afa-f276-4778-81e2-64e62767b180")  # Replace with the actual URL

        # Monitor the chat
        monitor_chat(browser)
    
    except Exception as e:
        print("An error occurred:", e)
    
    finally:
        # Close the browser window
        browser.quit()

if __name__ == "__main__":
    main()
