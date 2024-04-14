from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException
import time
import pyperclip  # For clipboard interactions
import re  # For regex operations
import os  # For file operations
import subprocess  # For code formatting
from config import BASE_REPO_PATH
import json


processed_messages = set()

def process_message(message_element, browser):
    """
    Process a single chat message, including extracting code snippets, handling remaining text,
    and executing actions.
    """
    message_id = message_element.get_attribute("data-message-id")
    if message_id not in processed_messages:
        message_text_element = message_element.find_element(By.CSS_SELECTOR, 'div.markdown.prose.w-full.break-words.dark\\:prose-invert.light > p')
        full_message_text = message_text_element.text

        # Attempt to click the "Copy code" button and extract the code snippet
        code_text = None
        try:
            copy_button = message_element.find_element(By.XPATH, './/button[contains(., "Copy code")]')
            scroll_into_view_and_click(browser, copy_button)
            time.sleep(1)  # Adjust the delay if needed
            code_text = pyperclip.paste()
            # Attempt to extract the remaining text after the code snippet
            try:
                remaining_text_element = message_element.find_element(By.XPATH, './/following-sibling::p')
                remaining_text = remaining_text_element.text
            except NoSuchElementException:
                remaining_text = ""  # No remaining text found
            # Update the full_message_text to include the code snippet explicitly if copied
            full_message_text += "\nCode snippet: " + code_text + "\n" + remaining_text
        except NoSuchElementException:
            print("Note: 'Copy code' button not found for message:", full_message_text)
            remaining_text = ""

        # Now parse and execute any action commands present in the message
        action, data_fields = parse_command(full_message_text)
        
        if action:
            print(f"Executing action: {action}")
            if action == "READ_FILE":
                file_content = read_file(data_fields)
                send_message(browser, file_content)
            elif action == "ADD_FILE":
                add_file(data_fields)
            elif action == "MODIFY_CODE":
                modify_code(data_fields)
                # Optionally, format the modified code
                format_code(data_fields.get('path'))
            # Handle other actions as needed
            print(f"Action processed: {action}, Message: {full_message_text}")
        else:
            # This handles messages without actions but includes code snippets and remaining text
            print("Message processed without actions:", full_message_text)
        
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

def monitor_chat(browser, chat_url):
    last_processed_id = load_last_processed_id(chat_url)

    while True:
        try:
            message_containers = WebDriverWait(browser, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[data-message-author-role="assistant"]')))
            
            # Initialize flag to start processing after the last known ID is found
            should_process = last_processed_id is None
            for container in message_containers:
                message_id = container.get_attribute("data-message-id")
                if message_id == last_processed_id:
                    should_process = True  # Start processing the next message
                    continue
                if should_process:
                    if wait_for_message_stable(browser, container):
                        process_message(container, browser)
                        save_last_processed_id(chat_url, message_id)  # Update with new last processed ID
        except Exception as e:
            print("An error occurred while monitoring chat:", e)
        time.sleep(5)  # Delay to prevent too frequent checks
        
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
    file_path = data.get('path')
    content = data.get('content', '')
    
    if not file_path:
        print("Error: File path not provided.")
        return
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as file:
        file.write(content)
    print(f"File created: {file_path}")


def modify_code(data):
    file_path = data.get('path')
    start_marker = re.escape(data.get('start_marker'))
    end_marker = re.escape(data.get('end_marker'))
    new_content = data.get('new_content', '')
    add_before = data.get('add_before')
    add_after = data.get('add_after')

    if not file_path or not (start_marker and end_marker or add_before or add_after):
        print("Error: Required data fields are missing.")
        return
    
    try:
        with open(file_path, 'r') as file:
            content = file.read()

        # For add_before or add_after, the logic will slightly differ
        if start_marker and end_marker:
            pattern = f"({start_marker})(.*?){end_marker}"
            content = re.sub(pattern, r'\1' + new_content + end_marker, content, flags=re.DOTALL)

        if add_before:
            pattern = f"^(?=.*{re.escape(add_before)})"  # Lookahead to match the whole line containing 'add_before' text
            content = re.sub(pattern, new_content + r'\n', content, flags=re.MULTILINE)
        
        if add_after:
            pattern = f"({re.escape(add_after)}.*?$)"  # Match the whole line containing 'add_after' text
            content = re.sub(pattern, r'\1' + '\n' + new_content, content, flags=re.MULTILINE)
        
        with open(file_path, 'w') as file:
            file.write(content)
        
        print(f"Code modifications applied in: {file_path}")
    except Exception as e:
        print(f"An error occurred while modifying the file: {e}")

def format_code(file_path):
    try:
        subprocess.run(["black", file_path], check=True)
        print(f"Code in {file_path} formatted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error formatting code: {e}")

def is_valid_path(base_path, action_path):
    # Resolve to absolute path and check if it starts with the base repository path
    full_path = os.path.abspath(os.path.join(base_path, action_path))
    return full_path.startswith(os.path.abspath(base_path))

def read_file(data):
    file_path = os.path.join(BASE_REPO_PATH, data.get('path', ''))
    if not is_valid_path(BASE_REPO_PATH, file_path):
        print("Error: Attempt to access invalid file path.")  # Logging
        return "Error: Attempt to access invalid file path."

    try:
        with open(file_path, 'r') as file:
            content = file.read()
        print(f"File content read successfully: {content[:100]}...")  # Logging first 100 chars
        return content
    except Exception as e:
        print(f"Error reading file: {str(e)}")  # Logging
        return f"Error reading file: {str(e)}"

def send_message(browser, message):
    try:
        # Find the message input area
        input_element = browser.find_element(By.ID, "prompt-textarea")
        # Clear the input area
        input_element.clear()
        # Type the message (file content) into the input area
        input_element.send_keys(message)  # Limit message length due to potential limitations
        # Press Enter to send (This may vary based on the specific chat interface)
        input_element.send_keys(Keys.ENTER)
    except Exception as e:
        print(f"Error sending message: {e}")

def save_last_processed_id(chat_url, last_id):
    try:
        with open('last_processed_ids.json', 'r') as file:
            ids = json.load(file)
    except FileNotFoundError:
        ids = {}

    ids[chat_url] = last_id

    with open('last_processed_ids.json', 'w') as file:
        json.dump(ids, file)

def load_last_processed_id(chat_url):
    try:
        with open('last_processed_ids.json', 'r') as file:
            ids = json.load(file)
        return ids.get(chat_url)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def scroll_into_view_and_click(browser, element):
    # Scroll the element into view
    browser.execute_script("arguments[0].scrollIntoView(true);", element)
    time.sleep(1)  # Brief pause to ensure scrolling completes
    # Attempt to click the element
    try:
        element.click()
        print("Element clicked successfully.")  # Logging
    except Exception as e:
        print(f"Error clicking element: {str(e)}")  # Logging

def main():
    # Initialize WebDriver with remote debugging port
    options = webdriver.ChromeOptions()
    options.debugger_address = "localhost:9333"
    browser = webdriver.Chrome(options=options)
    
    try:
        chat_url = "https://chat.openai.com/c/f7fc8afa-f276-4778-81e2-64e62767b180"  # Example URL
        browser.get(chat_url)
        monitor_chat(browser, chat_url)
    except Exception as e:
        print("An error occurred:", e)
    finally:
        browser.quit()

if __name__ == "__main__":
    main()
