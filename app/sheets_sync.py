import gspread
import json
import os
from google.oauth2.service_account import Credentials

def sync_to_payments_sheet(data):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds_json = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    client = gspread.authorize(creds)
    
    sheet = client.open("DocFlow").worksheet("Payments")
    
    new_row = [
        data.date,
        data.vendor_name,
        data.invoice_number,
        data.grand_total,
        data.tax,
        "Pending"
    ]
    sheet.append_row(new_row)