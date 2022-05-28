import json
import logging
import os
from threading import Timer
import requests
from dotenv import load_dotenv


def format_date(date):
    return date.strftime('%Y-%m-%dT%H:%M:%SZ')


class PayPalApi:

    def __init__(self):
        load_dotenv()
        self.PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
        self.PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
        self.PAYPAL_ENDPOINT = "https://api-m.paypal.com"
        self.PAYPAL_TOKEN = 0
        self.update_token()

    def get_transactions(self, start_date, end_date):
        url = self.PAYPAL_ENDPOINT + "/v1/reporting/transactions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.PAYPAL_TOKEN}"
        }

        payload = {
            'start_date': f'{format_date(start_date)}',
            'end_date': f'{format_date(end_date)}',
            'transaction_status': 'S',
            'fields': 'cart_info, payer_info'
        }

        response = requests.get(url, headers=headers, params=payload)

        return json.loads(response.text)

    def update_token(self):
        url = self.PAYPAL_ENDPOINT + '/v1/oauth2/token'

        payload = {
            "grant_type": "client_credentials"
        }

        response = requests.post(url, auth=(self.PAYPAL_CLIENT_ID, self.PAYPAL_CLIENT_SECRET), data=payload)
        data = response.json()

        # keep the token alive
        token_expire = int(data['expires_in']) - 60
        t = Timer(token_expire, self.update_token)
        t.daemon = True
        t.start()

        logging.info(f"Got new access token.")
        self.PAYPAL_TOKEN = data['access_token']
