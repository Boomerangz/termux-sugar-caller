import requests
import time
from datetime import datetime, timedelta
import subprocess
import json
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

@dataclass
class Config:
    URL: str = 'https://functions.yandexcloud.net/d4e0ut514kko74alvvqm'
    FETCH_INTERVAL: int = 180  # Fetch every 3 minutes
    MG_DL_TO_MOL_L: float = 0.0555
    TARGET_MOL_L: float = 5.9
    TARGET_MOL_L_MAX: float = 9.0
    TARGET_MOL_L_PERFECT: float = 6.9
    PREDICTION_HOUR: float = 0.8
    SMS_RECIPIENT: str = '+79956282117'
    SMS_MESSAGE_ZERO: str = 'basal 0'
    SMS_MESSAGE_MAX_BASAL: str = 'basal 0.6'
    SMS_MESSAGE_CANCEL: str = 'basal cancel'
    ALERT_COOLDOWN: timedelta = timedelta(hours=0.5)
    SMS_CHECK_INTERVAL: int = 60
    CODE_PATTERN: str = r'\b[A-Za-z]{3}\b'
    RESPONSE_WINDOW: timedelta = timedelta(minutes=3)
    RESPONSE_CHECK_INTERVAL: int = 10

class SMSHandler:
    def __init__(self, config: Config):
        self.config = config
        self.last_alert_time: Optional[datetime] = None
        self.last_alert_type: Optional[str] = None
        self.last_processed_sms_id: Optional[int] = None
        self.awaiting_response: bool = False
        self.response_handled: bool = False
        self.alert_sent_time: Optional[datetime] = None

    def send_sms(self, recipient: str, message: str) -> None:
        """
        Sends an SMS using Termux API.
        """
        try:
            subprocess.run(['termux-sms-send', '-n', recipient, message], check=True)
            logging.info(f"SMS sent to {recipient}: '{message}'")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to send SMS: {e}")

    def fetch_incoming_sms(self) -> List[Dict]:
        """
        Fetches incoming SMS messages using Termux API.
        Returns a list of messages sorted by ID in ascending order.
        """
        try:
            result = subprocess.run(['termux-sms-list', '-l', '50'], capture_output=True, text=True, check=True)
            messages = json.loads(result.stdout)
            messages_sorted = sorted(messages, key=lambda x: int(x['_id']), reverse=True)
            return messages_sorted
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to fetch SMS messages: {e}")
            return []
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse SMS messages: {e}")
            return []

    def should_send_alert(self, current_time: datetime, alert_type: str) -> bool:
        """
        Determines whether an alert should be sent based on cooldown and alert type.
        """
        if self.last_alert_time is None:
            return True
        if (current_time - self.last_alert_time >= self.config.ALERT_COOLDOWN and
                self.last_alert_type == alert_type):
            return True
        return False

    def process_incoming_sms(self) -> bool:
        """
        Processes incoming SMS messages, identifies three-letter codes, and responds.
        Only processes if awaiting_response is True and within RESPONSE_WINDOW.
        """
        if not self.awaiting_response:
            logging.debug("Not awaiting a response, skipping SMS processing.")
            return False

        current_time = datetime.now()
        if self.alert_sent_time and (current_time - self.alert_sent_time > self.config.RESPONSE_WINDOW):
            logging.warning("Response window expired. No response received.")
            self.awaiting_response = False
            self.response_handled = False
            return False

        messages = self.fetch_incoming_sms()
        new_messages = [
            msg for msg in messages
            if self.last_processed_sms_id is None or int(msg.get('_id', 0)) > self.last_processed_sms_id
        ]

        for msg in new_messages:
            sender = msg.get('number')
            content = msg.get('body', '')
            msg_id = int(msg.get('_id', 0))
            logging.info(f"New SMS from {sender}: '{content}'")

            # Update last_processed_sms_id
            self.last_processed_sms_id = msg_id

            # Check for three-letter code
            match = re.search(self.config.CODE_PATTERN, content)
            if match:
                code = match.group(0)
                logging.info(f"Three-letter code '{code}' found. Sending back to {sender}.")
                self.send_sms(sender, code)
                self.response_handled = True
                self.awaiting_response = False
                return True
            else:
                logging.debug("No three-letter code found in the message.")

        logging.debug("No new SMS messages with valid codes during response window.")
        return False

    def send_sms_and_approve(self, message: str) -> None:
        """
        Sends an SMS and waits for approval by handling incoming responses.
        """
        self.send_sms(self.config.SMS_RECIPIENT, message)
        time.sleep(15)  # Wait briefly after sending SMS

        self.last_alert_time = datetime.now()
        self.alert_sent_time = self.last_alert_time
        self.awaiting_response = True

        while self.awaiting_response:
            logging.debug("Checking for SMS response...")
            processed = self.process_incoming_sms()
            if processed:
                logging.info(f"SMS approved with message: '{message}'")
                break
            logging.debug(f"Awaiting response... (sleeping for {self.config.RESPONSE_CHECK_INTERVAL} seconds)")
            time.sleep(self.config.RESPONSE_CHECK_INTERVAL)

class GlucoseMonitor:
    def __init__(self, config: Config, sms_handler: SMSHandler):
        self.config = config
        self.sms_handler = sms_handler

    def fetch_data(self) -> Optional[Dict]:
        """
        Fetches glucose data from the specified URL.
        """
        try:
            response = requests.get(self.config.URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data:
                return data[0]  # Assuming the latest entry is the first in the list
            else:
                logging.warning("No data received from the server.")
                return None
        except requests.RequestException as e:
            logging.error(f"Error fetching data: {e}")
            return None

    def convert_to_mmol_l(self, mg_dl: float) -> float:
        """
        Converts glucose level from mg/dL to mmol/L.
        """
        return mg_dl * self.config.MG_DL_TO_MOL_L

    def predict_glucose(self, current_mmol_l: float, delta_per_min: float) -> float:
        """
        Predicts the glucose level after a certain number of hours.
        """
        projected = current_mmol_l + (delta_per_min * 60 * self.config.PREDICTION_HOUR)
        return projected

    def should_send_alert(self, current_time: datetime, alert_type: str) -> bool:
        """
        Determines if an alert should be sent based on cooldown and alert type.
        """
        return self.sms_handler.should_send_alert(current_time, alert_type)

    def handle_alert(self, projected_glucose: float, alert_type: str) -> None:
        """
        Sends appropriate SMS alert based on the alert type.
        """
        message = (self.config.SMS_MESSAGE_ZERO if alert_type == 'min' 
                   else self.config.SMS_MESSAGE_MAX_BASAL if alert_type == 'max' else self.config.SMS_MESSAGE_CANCEL)
        self.sms_handler.send_sms_and_approve(message)
        self.sms_handler.last_alert_type = alert_type

    def run(self) -> None:
        """
        Main loop for monitoring glucose levels and handling alerts.
        """
        logging.info("Starting glucose monitoring script with conditional SMS alert and response...")
        while True:
            current_time = datetime.now()
            entry = self.fetch_data()

            if entry:
                current_sgv_mg_dl = entry.get('sgv')
                if current_sgv_mg_dl is None:
                    logging.warning("'sgv' field missing in data.")
                else:
                    current_mmol_l = self.convert_to_mmol_l(current_sgv_mg_dl)

                    delta_mg_dl = entry.get('delta', 0) or 0
                    delta_mmol_l_per_min = (delta_mg_dl * self.config.MG_DL_TO_MOL_L) / (self.config.FETCH_INTERVAL / 60)

                    projected_glucose = self.predict_glucose(current_mmol_l, delta_mmol_l_per_min)

                    logging.info(
                        f"Current Glucose: {current_mmol_l:.2f} mmol/L, "
                        f"Delta: {delta_mmol_l_per_min:.4f} mmol/L/min"
                    )
                    logging.info(f"Projected Glucose in {self.config.PREDICTION_HOUR} hour(s): {projected_glucose:.2f} mmol/L")

                    if projected_glucose < self.config.TARGET_MOL_L:
                        logging.warning(
                            f"⚠️ ALERT: Glucose is projected to reach {projected_glucose:.2f} mmol/L in "
                            f"{self.config.PREDICTION_HOUR} hour(s)."
                        )
                        if self.should_send_alert(current_time, 'min'):
                            self.handle_alert(projected_glucose, 'min')
                        else:
                            logging.info("Alert already sent within the cooldown period.")
                    elif (projected_glucose > self.config.TARGET_MOL_L_MAX and 
                          current_mmol_l > self.config.TARGET_MOL_L_PERFECT):
                        logging.warning(
                            f"⚠️ ALERT: Glucose is projected to reach {projected_glucose:.2f} mmol/L in "
                            f"{self.config.PREDICTION_HOUR} hour(s)."
                        )
                        if self.should_send_alert(current_time, 'max'):
                            self.handle_alert(projected_glucose, 'max')
                    elif self.last_alert_time  and datetime.now() - self.last_alert_time < self.config.ALERT_COOLDOWN:
                        logging.warning(
                            f"⚠️ ALERT: Glucose is normal. Canceling temporary basal"
                        )
                        if self.should_send_alert(current_time, 'cancel'):
                            self.handle_alert(projected_glucose, 'cancel')
                    else:
                        logging.info("Glucose level is within safe range.")

            time.sleep(self.config.FETCH_INTERVAL)

def main():
    config = Config()
    sms_handler = SMSHandler(config)
    glucose_monitor = GlucoseMonitor(config, sms_handler)
    glucose_monitor.run()

if __name__ == "__main__":
    main()
