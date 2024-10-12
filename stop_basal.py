import requests
import time
from datetime import datetime, timedelta
import subprocess
import json
import re

# Constants
URL = 'https://mark.zygin.dev/api/v1/entries/current.json'
FETCH_INTERVAL = 300  # Fetch every 5 minutes (300 seconds)
MG_DL_TO_MOL_L = 0.0555  # Conversion factor from mg/dL to mmol/L
TARGET_MOL_L = 5.5  # Target glucose level in mmol/L for SMS alert
PREDICTION_HOUR = 1  # Prediction time in hours
SMS_RECIPIENT = '+1234567890'  # Replace with the recipient's phone number
SMS_MESSAGE = 'basal 0'
ALERT_COOLDOWN = timedelta(hours=1)  # Minimum time between SMS alerts

SMS_CHECK_INTERVAL = 60  # Check for new SMS every 60 seconds
CODE_PATTERN = r'\b[A-Za-z]{3}\b'  # Regex pattern for three-letter codes

# Global variables
last_alert_time = None
last_processed_sms_id = None

def fetch_data(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]  # Assuming the latest entry is the first in the list
        else:
            print(f"[{datetime.now()}] No data received.")
            return None
    except requests.RequestException as e:
        print(f"[{datetime.now()}] Error fetching data: {e}")
        return None

def convert_to_mmol_l(mg_dl):
    return mg_dl * MG_DL_TO_MOL_L

def predict_glucose(current_mmol_l, delta_per_min):
    """
    Predicts the glucose level after a certain number of minutes.
    delta_per_min: rate of change per minute in mmol/L
    """
    projected = current_mmol_l + (delta_per_min * 60 * PREDICTION_HOUR)
    return projected

def send_sms(recipient, message):
    """
    Sends an SMS using Termux API.
    """
    try:
        subprocess.run(['termux-sms-send', '-n', recipient, message], check=True)
        print(f"[{datetime.now()}] SMS sent to {recipient}: '{message}'")
    except subprocess.CalledProcessError as e:
        print(f"[{datetime.now()}] Failed to send SMS: {e}")

def should_send_alert(current_time):
    global last_alert_time
    if last_alert_time is None:
        return True
    if current_time - last_alert_time >= ALERT_COOLDOWN:
        return True
    return False

def fetch_incoming_sms():
    """
    Fetches incoming SMS messages using Termux API.
    Returns a list of messages sorted by ID in ascending order.
    """
    try:
        result = subprocess.run(['termux-messaging-list', '-l', '50'], capture_output=True, text=True, check=True)
        messages = json.loads(result.stdout)
        # Sort messages by ID in ascending order
        messages_sorted = sorted(messages, key=lambda x: int(x['id']))
        return messages_sorted
    except subprocess.CalledProcessError as e:
        print(f"[{datetime.now()}] Failed to fetch SMS messages: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] Failed to parse SMS messages: {e}")
        return []

def process_incoming_sms():
    """
    Processes incoming SMS messages, identifies three-letter codes, and responds.
    """
    global last_processed_sms_id
    messages = fetch_incoming_sms()
    new_messages = []

    for msg in messages:
        msg_id = int(msg.get('id', 0))
        if last_processed_sms_id is None or msg_id > last_processed_sms_id:
            new_messages.append(msg)

    if new_messages:
        for msg in new_messages:
            sender = msg.get('address')
            content = msg.get('body', '')
            msg_id = int(msg.get('id', 0))
            print(f"[{datetime.now()}] New SMS from {sender}: '{content}'")
            # Check for three-letter code
            match = re.search(CODE_PATTERN, content)
            if match:
                code = match.group(0)
                print(f"[{datetime.now()}] Three-letter code '{code}' found. Sending back to {sender}.")
                send_sms(sender, code)
            else:
                print(f"[{datetime.now()}] No three-letter code found in the message.")
            # Update the last processed SMS ID
            if last_processed_sms_id is None or msg_id > last_processed_sms_id:
                last_processed_sms_id = msg_id
    else:
        print(f"[{datetime.now()}] No new SMS messages.")

def main():
    global last_alert_time
    print("Starting glucose monitoring script with SMS alert and response...")
    last_sms_check = datetime.now() - timedelta(seconds=SMS_CHECK_INTERVAL)
    while True:
        current_time = datetime.now()

        # Fetch and process glucose data
        entry = fetch_data(URL)
        if entry:
            # Extract current glucose in mg/dL and convert to mmol/L
            current_sgv_mg_dl = entry.get('sgv')
            if current_sgv_mg_dl is None:
                print(f"[{current_time}] 'sgv' field missing in data.")
            else:
                current_mmol_l = convert_to_mmol_l(current_sgv_mg_dl)

                # Extract delta (change in mg/dL since last reading)
                delta_mg_dl = entry.get('delta', 0)
                if delta_mg_dl is None:
                    print(f"[{current_time}] 'delta' field missing in data.")
                    delta_mg_dl = 0
                # To compute rate per minute, divide delta by FETCH_INTERVAL in seconds and multiply by 60
                # This assumes delta is the total change since the last reading
                delta_mmol_l_per_min = (delta_mg_dl * MG_DL_TO_MOL_L) / (FETCH_INTERVAL / 60)

                # Predict glucose after 1 hour
                projected_glucose = predict_glucose(current_mmol_l, delta_mmol_l_per_min)

                print(f"[{current_time}] Current Glucose: {current_mmol_l:.2f} mmol/L, Delta: {delta_mmol_l_per_min:.4f} mmol/L/min")
                print(f"Projected Glucose in {PREDICTION_HOUR} hour(s): {projected_glucose:.2f} mmol/L")

                if projected_glucose < TARGET_MOL_L:
                    print(f"⚠️ ALERT: Glucose is projected to reach {projected_glucose:.2f} mmol/L in {PREDICTION_HOUR} hour(s).")
                    if should_send_alert(current_time):
                        send_sms(SMS_RECIPIENT, SMS_MESSAGE)
                        last_alert_time = current_time
                    else:
                        print(f"[{current_time}] Alert already sent within the cooldown period.")
                else:
                    print("Glucose level is within safe range.")

        # Check for incoming SMS messages at defined intervals
        if (current_time - last_sms_check) >= timedelta(seconds=SMS_CHECK_INTERVAL):
            process_incoming_sms()
            last_sms_check = current_time

        # Wait for the next fetch
        time.sleep(FETCH_INTERVAL)

if __name__ == "__main__":
    main()
