import requests
import time
import threading
import mysql.connector

# Replace with your bot token
BOT_TOKEN = '7400842411:AAHcbbJDLdZ0BTMfzk0VGHG5pmNeb4720EY'
API_URL = f'https://api.telegram.org/bot{BOT_TOKEN}'

# Replace with the chat ID of the source and destination channels
SOURCE_CHANNEL_ID = -1002233847705  # Use negative ID for channels
DESTINATION_CHANNEL_IDS = [-1002212902820, -1002212743926]  # Use negative ID for channels

auto_forward = False

# Initialize MySQL connection
conn = mysql.connector.connect(
    host='Aadity.mysql.pythonanywhere-services.com',  # Replace with your MySQL server address
    user='Aadity',  # Replace with your MySQL username
    password='Urmi@1011',  # Replace with your MySQL password
    database='Aadity$test_db'  # Replace with your MySQL database name
)


cursor = conn.cursor()

# Create table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS forward (
        original_message_id BIGINT,
        destination_message_id BIGINT,
        destination_chat_id BIGINT,
        original_quote_message_id BIGINT,
        destination_quote_message_id BIGINT
    )
''')
conn.commit()


def keep_alive(conn, interval=300):
    """Keep the MySQL connection alive by pinging it periodically."""
    while True:
        conn.ping(reconnect=True, attempts=3, delay=5)
        time.sleep(interval)


def get_updates(offset=None):
    """Get updates from the Telegram API."""
    url = f'{API_URL}/getUpdates'
    params = {'timeout': 100, 'offset': offset}
    response = requests.get(url, params=params)
    result_json = response.json()['result']
    return result_json

def send_message(chat_id, text, reply_to_message_id=None):
    """Send a text message to a channel, optionally quoting another message."""
    url = f'{API_URL}/sendMessage'
    data = {'chat_id': chat_id, 'text': text}
    if reply_to_message_id:
        data['reply_to_message_id'] = reply_to_message_id
    response = requests.post(url, data=data)
    return response.json()

def forward_message(chat_id, from_chat_id, message_id):
    """Forward a message to a channel without showing forward tag."""
    url = f'{API_URL}/copyMessage'
    data = {'chat_id': chat_id, 'from_chat_id': from_chat_id, 'message_id': message_id}
    response = requests.post(url, data=data)
    return response.json()

def store_message_id(original_message_id, destination_message_id=None, destination_chat_id=None, original_quote_message_id=None, destination_quote_message_id=None):
    """Store the mapping of original and forwarded message IDs in the MySQL database."""
    cursor.execute('''
        INSERT INTO forward (original_message_id, destination_message_id, destination_chat_id, original_quote_message_id, destination_quote_message_id)
        VALUES (%s, %s, %s, %s, %s)
    ''', (original_message_id, destination_message_id, destination_chat_id, original_quote_message_id, destination_quote_message_id))
    conn.commit()

def get_message_id(original_message_id, destination_chat_id):
    """Retrieve the forwarded message ID for a given original message ID and destination chat ID."""
    cursor.execute('''
        SELECT destination_message_id FROM forward
        WHERE original_message_id = %s AND destination_chat_id = %s
    ''', (original_message_id, destination_chat_id))
    result = cursor.fetchone()
    return result[0] if result else None

def get_quoted_message_id(original_quote_message_id, destination_chat_id):
    """Retrieve the forwarded message ID for a given original quote message ID and destination chat ID."""
    cursor.execute('''
        SELECT destination_message_id FROM forward
        WHERE original_message_id = %s AND destination_chat_id = %s
    ''', (original_quote_message_id, destination_chat_id))
    result = cursor.fetchone()
    return result[0] if result else None

def main():
    """Main function to run the bot."""
    global auto_forward
    update_id = None

    # Start the keep-alive thread
    keep_alive_thread = threading.Thread(target=keep_alive, args=(conn,))
    keep_alive_thread.daemon = True
    keep_alive_thread.start()

    while True:
        updates = get_updates(offset=update_id)

        for update in updates:
            if 'update_id' in update:
                update_id = update['update_id'] + 1

            if 'message' in update:
                message = update['message']
                chat_id = message['chat']['id']
                text = message.get('text', '')

                if text == '/start' and not auto_forward:
                    auto_forward = True
                    send_message(chat_id, "Auto-forwarding started.")
                elif text == '/stop' and auto_forward:
                    auto_forward = False
                    send_message(chat_id, "Auto-forwarding stopped.")

            if 'channel_post' in update and update['channel_post']['chat']['id'] == SOURCE_CHANNEL_ID:
                channel_post = update['channel_post']
                message_id = channel_post['message_id']
                reply_to_message = channel_post.get('reply_to_message')

                original_quote_message_id = None
                if reply_to_message:
                    original_quote_message_id = reply_to_message['message_id']

                # Store the original message ID in the database
                store_message_id(original_message_id=message_id)

                if auto_forward:
                    for dest_channel_id in DESTINATION_CHANNEL_IDS:
                        if original_quote_message_id:
                            destination_quote_message_id = get_quoted_message_id(original_quote_message_id, dest_channel_id)
                        else:
                            destination_quote_message_id = None

                        if destination_quote_message_id:
                            # Send the message with the quote
                            sent_message = send_message(chat_id=dest_channel_id, text=channel_post['text'], reply_to_message_id=destination_quote_message_id)
                            if 'result' in sent_message:
                                sent_message_id = sent_message['result']['message_id']
                                store_message_id(message_id, sent_message_id, dest_channel_id, original_quote_message_id, destination_quote_message_id)
                        else:
                            # Forward the message
                            forwarded_message = forward_message(chat_id=dest_channel_id, from_chat_id=SOURCE_CHANNEL_ID, message_id=message_id)
                            if 'result' in forwarded_message:
                                forwarded_message_id = forwarded_message['result']['message_id']
                                store_message_id(message_id, forwarded_message_id, dest_channel_id, original_quote_message_id, destination_quote_message_id)
                                if original_quote_message_id:
                                    # Store the quote mapping
                                    store_message_id(original_quote_message_id, forwarded_message_id, dest_channel_id)

        time.sleep(1)

if __name__ == '__main__':
    main()