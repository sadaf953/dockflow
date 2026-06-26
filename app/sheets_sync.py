import gspread

def sync_to_payments_sheet(data):
    client = gspread.oauth(
        credentials_filename="client_secrets.json"
    )
    
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