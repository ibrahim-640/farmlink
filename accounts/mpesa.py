import requests
import base64
from datetime import datetime
from decouple import config
from requests.auth import HTTPBasicAuth

# Load credentials from .env
MPESA_SHORTCODE = config("MPESA_SHORTCODE")
MPESA_PASSKEY = config("MPESA_PASSKEY")
MPESA_CALLBACK_URL = config("MPESA_CALLBACK_URL")
MPESA_CONSUMER_KEY = config("MPESA_CONSUMER_KEY")
MPESA_CONSUMER_SECRET = config("MPESA_CONSUMER_SECRET")


def get_access_token():
    """
    Generate M-Pesa OAuth access token dynamically using consumer key and secret.
    """
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    try:
        response = requests.get(url, auth=HTTPBasicAuth(MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET))
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if not token:
            print("Failed to retrieve access token:", data)
        return token
    except requests.RequestException as e:
        print("Error generating access token:", e)
        return None


def lipa_na_mpesa(phone_number, amount, account_reference, transaction_desc):
    """
    Perform Lipa Na M-Pesa STK Push payment.
    """
    amount = int(amount)  # Convert to int as M-Pesa does not accept decimals

    # Generate timestamp and password
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password_str = f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(password_str.encode()).decode()

    # Get dynamic access token
    access_token = get_access_token()
    if not access_token:
        return {"error": "Failed to generate access token"}

    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_desc
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            print("M-Pesa response is not JSON:", resp.text)
            data = {"error": resp.text}
    except requests.HTTPError as http_err:
        print("HTTP error occurred:", http_err)
        data = {"error": str(http_err), "response_text": resp.text}
    except requests.RequestException as req_err:
        print("Request exception:", req_err)
        data = {"error": str(req_err)}

    # Debug info
    print("Payload sent:", payload)
    print("Response received:", data)

    return data
