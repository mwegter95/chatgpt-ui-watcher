from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

processed_messages = set()

def process_message(message_element):
    """
    Process a single chat message.
    """
    message_id = message_element.get_attribute("data-message-id")
    if message_id not in processed_messages:
        message_text_element = message_element.find_element(By.CSS_SELECTOR, 'div.markdown.prose.w-full.break-words.dark\\:prose-invert.light > p')
        message_text = message_text_element.text
        # Add your message processing logic here
        print("Message:", message_text)
        # Mark the message as processed
        processed_messages.add(message_id)

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
                process_message(container)
        
        except Exception as e:
            print("An error occurred while monitoring chat:", e)

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
