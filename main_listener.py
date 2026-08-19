import time
import base64
import re
from googleapiclient.discovery import build
from google_service import get_google_credentials, log_ticket_to_sheet, send_email_response
from crew_pipeline import process_ticket
from guardrails import run_input_guardrails

PROCESSED_MESSAGE_IDS = set()

IGNORE_SENDERS = [
    "drive-shares-dm-noreply@google.com",
    "workspace-noreply@google.com",
    "no-reply",
    "noreply",
    "mailer-daemon",
    "arunappan.ai@gmail.com"  # Ignore self to avoid loop
]


def get_gmail_service():
    """Authenticates and returns the Gmail API discovery service instance."""
    creds = get_google_credentials()
    return build('gmail', 'v1', credentials=creds)


def extract_body(payload):
    """Recursively extracts plain text body from the Gmail message payload."""
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part['body'].get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            elif 'parts' in part:
                extracted = extract_body(part)
                if extracted:
                    return extracted
    elif 'body' in payload and 'data' in payload['body']:
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
    return ""


def clean_reply_text(body: str) -> str:
    """Strips out quoted reply headers (e.g., 'On Wed, Aug 19... wrote:') and block quotes."""
    lines = body.splitlines()
    cleaned = []
    for line in lines:
        if re.match(r"^On\s+.+wrote:\s*$", line.strip(), re.IGNORECASE):
            break
        if line.strip().startswith(">"):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    return result if result else body.strip()


def should_skip_email(sender_email: str) -> bool:
    """Filters out automated bot alerts and system notifications."""
    sender_lower = sender_email.lower()
    for ignored in IGNORE_SENDERS:
        if ignored in sender_lower:
            return True
    return False


def get_thread_history_from_gmail(service, thread_id: str, current_msg_id: str):
    """
    Fetches past messages in this thread directly from Gmail to provide accurate conversational memory.
    """
    try:
        thread = service.users().threads().get(userId='me', id=thread_id, format='full').execute()
        thread_messages = thread.get('messages', [])
        history_lines = []

        for m in thread_messages:
            if m['id'] == current_msg_id:
                continue

            headers = m['payload'].get('headers', [])
            sender = "Unknown"
            for h in headers:
                if h.get('name', '').lower() == 'from':
                    sender_val = h.get('value', '')
                    sender = sender_val.split('<')[1].split('>')[0] if '<' in sender_val else sender_val
                    break

            msg_body = clean_reply_text(extract_body(m['payload'])).strip()
            if msg_body:
                role = "Support" if "arunappan.ai" in sender.lower() else "Customer"
                history_lines.append(f"{role}: {msg_body}")

        return history_lines
    except Exception as e:
        print(f"⚠️ Warning: Could not fetch Gmail thread history: {e}")
        return []


def check_and_process_emails():
    """Polls Gmail for unread customer messages, applies guardrails, and triggers CrewAI."""
    service = get_gmail_service()
    results = service.users().messages().list(userId='me', q='is:unread').execute()
    messages = results.get('messages', [])
    
    if not messages:
        print("⏳ [Inbox Monitor] No new customer emails found. Waiting...")
        return

    for msg_meta in messages:
        msg_id = msg_meta['id']
        if msg_id in PROCESSED_MESSAGE_IDS:
            continue

        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        thread_id = msg.get('threadId')
        headers = msg['payload'].get('headers', [])
        
        sender_email = ""
        subject = "No Subject"
        message_id_header = None

        for header in headers:
            name = header.get('name', '').lower()
            if name == 'from':
                sender_raw = header.get('value', '')
                if '<' in sender_raw:
                    sender_email = sender_raw.split('<')[1].split('>')[0].strip()
                else:
                    sender_email = sender_raw.strip()
            elif name == 'subject':
                subject = header.get('value', '')
            elif name == 'message-id':
                message_id_header = header.get('value', '')

        # Mark as read immediately in Gmail
        try:
            service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        except Exception as err:
            print(f"⚠️ Failed to mark email as read: {err}")

        PROCESSED_MESSAGE_IDS.add(msg_id)

        # Skip system notifications or self-sent emails
        if should_skip_email(sender_email):
            print(f"🚫 Ignored automated/system email from: {sender_email}")
            continue

        raw_body = extract_body(msg['payload']).strip()
        body = clean_reply_text(raw_body)

        if not body:
            print(f"⚠️ Empty body from {sender_email}. Skipping.")
            continue

        ticket_id = f"TICK-{thread_id[:6].upper()}"

        print(f"\n==========================================")
        print(f"🎟️ Processing Ticket: {ticket_id}")
        print(f"👤 From: {sender_email}")
        print(f"📌 Subject: {subject}")
        print(f"🧵 Thread ID: {thread_id}")
        print(f"📝 Customer Query: {body}")
        print(f"==========================================")

        start_time = time.perf_counter()

        # ----------------- ENTERPRISE INPUT GUARDRAIL -----------------
        is_safe, alert_reason = run_input_guardrails(body)
        if not is_safe:
            print(f"🛡️ Guardrail Blocked: {alert_reason}")
            elapsed_time = time.perf_counter() - start_time
            
            rejection_body = (
                f"Dear Customer,\n\n"
                f"{alert_reason}\n\n"
                f"If you have a genuine airline booking or policy question, please feel free to ask.\n\n"
                f"Best regards,\n"
                f"SkyRoute Security & Support Team"
            )
            
            # Send immediate security reply without invoking LLM
            send_email_response(
                to_email=sender_email,
                subject=subject,
                body=rejection_body,
                thread_id=thread_id,
                message_id_header=message_id_header
            )
            
            # Log security block in Google Sheet
            log_ticket_to_sheet(
                ticket_id=ticket_id,
                sender_email=sender_email,
                subject=subject,
                query=body,
                score="0%",
                source="Guardrail Filter (Blocked)",
                response=alert_reason,
                response_time=elapsed_time
            )
            print(f"⏱️ Guardrail Intervention Time: {elapsed_time:.2f} seconds\n")
            continue
        # --------------------------------------------------------------

        # Fetch chronological conversation history directly from Gmail API
        past_turns = get_thread_history_from_gmail(service, thread_id, current_msg_id=msg_id)

        if past_turns:
            formatted_history = "\n".join([f"- {turn}" for turn in past_turns])
            augmented_query = (
                f"### CONVERSATION HISTORY FOR THIS THREAD:\n{formatted_history}\n\n"
                f"### CURRENT CUSTOMER QUERY:\n{body}"
            )
        else:
            augmented_query = (
                f"### CONVERSATION HISTORY FOR THIS THREAD:\n(No previous messages. This is the first question from the customer.)\n\n"
                f"### CURRENT CUSTOMER QUERY:\n{body}"
            )

        # Kick off CrewAI Multi-Agent Pipeline
        crew_output = process_ticket(
            ticket_id=ticket_id,
            sender_email=sender_email,
            subject=subject,
            customer_query=augmented_query,
            thread_id=thread_id,
            message_id_header=message_id_header
        )

        elapsed_time = time.perf_counter() - start_time

        # Log resolved ticket details to Google Sheets
        log_ticket_to_sheet(
            ticket_id=ticket_id,
            sender_email=sender_email,
            subject=subject,
            query=body,
            score=">=70%",
            source="Knowledge Base / Thread History",
            response=str(crew_output),
            response_time=elapsed_time
        )

        print(f"⏱️ Total Response Time: {elapsed_time:.2f} seconds")
        print(f"✅ Successfully resolved and replied to Ticket [{ticket_id}].\n")


def start_polling(interval_seconds=5):
    """Starts the continuous polling loop for incoming support emails."""
    print("🚀 SkyRoute Autonomous Ticketing System is LIVE!")
    print(f"Listening for customer queries every {interval_seconds} seconds...\n")
    while True:
        try:
            check_and_process_emails()
        except Exception as e:
            print(f"⚠️ Polling error: {str(e)}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    start_polling(5)