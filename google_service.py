import os
import base64
from email.mime.text import MIMEText
from datetime import datetime
import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes needed for Gmail read/send and Google Sheets read/write
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
SHEET_NAME = 'SkyRoute Support Tickets'


def get_google_credentials():
    """Authenticates and returns valid OAuth2 user credentials."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' not found! Please download OAuth credentials from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for subsequent runs
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            
    return creds


def log_ticket_to_sheet(ticket_id: str, sender_email: str, subject: str, query: str, 
                        score: str = "N/A", source: str = "Knowledge Base", 
                        response: str = "Completed", response_time: float = 0.0):
    """Appends a new ticket record with response latency to Google Sheets."""
    try:
        creds = get_google_credentials()
        gc = gspread.authorize(creds)
        spreadsheet = gc.open(SHEET_NAME)
        worksheet = spreadsheet.sheet1
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            str(ticket_id),
            str(sender_email),
            str(subject),
            str(query),
            str(score),
            str(source),
            str(response),
            str(timestamp),
            f"{response_time:.2f}s"
        ]
        
        worksheet.append_row(row, value_input_option='USER_ENTERED')
        print(f"📊 Ticket [{ticket_id}] logged to Google Sheet. (Latency: {response_time:.2f}s)")
        return True
    except Exception as e:
        print(f"⚠️ Failed to log ticket to Google Sheets: {str(e)}")
        return False


def send_email_response(to_email: str, subject: str, body: str, thread_id: str = None, message_id_header: str = None) -> bool:
    """Sends the drafted email reply into the existing thread via Gmail API."""
    try:
        creds = get_google_credentials()
        service = build('gmail', 'v1', credentials=creds)

        message = MIMEText(body)
        message['to'] = to_email
        message['subject'] = subject if subject.lower().startswith("re:") else f"Re: {subject}"

        # Standard threading headers required by Gmail & email clients
        if message_id_header:
            message['In-Reply-To'] = message_id_header
            message['References'] = message_id_header

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        body_payload = {'raw': raw_message}
        
        if thread_id:
            body_payload['threadId'] = thread_id

        send_res = service.users().messages().send(userId='me', body=body_payload).execute()
        print(f"📧 Threaded email reply sent to {to_email} (Thread ID: {thread_id})")
        return True
    except Exception as e:
        print(f"⚠️ Failed to send email via Gmail API: {str(e)}")
        return False


if __name__ == "__main__":
    print("Testing Google Authentication & Connectivity...")
    credentials = get_google_credentials()
    print("✅ Authentication successful! token.json generated.")