"""
Gmail Sender Module.
Sends emails via Gmail using app password authentication.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
from datetime import datetime, date
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import time

from ..config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAILS_PER_MINUTE, DAILY_EMAIL_CAP


# Thread pool for blocking SMTP operations
_executor = ThreadPoolExecutor(max_workers=2)

# Daily send tracking
_daily_send_count = 0
_last_send_date: Optional[date] = None


def _reset_daily_count_if_needed():
    """Reset daily count if it's a new day."""
    global _daily_send_count, _last_send_date
    today = date.today()
    if _last_send_date != today:
        _daily_send_count = 0
        _last_send_date = today


def get_daily_send_count() -> int:
    """Get the current daily send count."""
    _reset_daily_count_if_needed()
    return _daily_send_count


def get_remaining_daily_quota() -> int:
    """Get remaining emails that can be sent today."""
    return max(0, DAILY_EMAIL_CAP - get_daily_send_count())


def _send_email_sync(
    to_email: str,
    subject: str,
    body: str,
    from_email: str = None,
    from_name: str = None
) -> Tuple[bool, str]:
    """
    Synchronous email sending via Gmail SMTP.
    
    Returns:
        Tuple of (success, message)
    """
    global _daily_send_count
    
    if from_email is None:
        from_email = GMAIL_ADDRESS
    
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return False, "Gmail credentials not configured"
    
    # Check daily limit
    _reset_daily_count_if_needed()
    if _daily_send_count >= DAILY_EMAIL_CAP:
        return False, f"Daily email cap reached ({DAILY_EMAIL_CAP})"
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{from_email}>" if from_name else from_email
        msg['To'] = to_email
        
        # Plain text version
        text_part = MIMEText(body, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # HTML version (simple conversion)
        html_body = body.replace('\n', '<br>')
        html_body = f"<html><body><p>{html_body}</p></body></html>"
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Connect to Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(from_email, to_email, msg.as_string())
        
        # Update daily count
        _daily_send_count += 1
        
        return True, "Email sent successfully"
        
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed. Check your app password."
    except smtplib.SMTPRecipientsRefused:
        return False, f"Recipient refused: {to_email}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Error sending email: {str(e)}"


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: str = None,
    from_name: str = None
) -> Tuple[bool, str]:
    """
    Async wrapper for sending email.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _send_email_sync,
        to_email,
        subject,
        body,
        from_email,
        from_name
    )


async def send_emails_batch(
    emails: list,
    rate_limit: int = None
) -> list:
    """
    Send multiple emails with rate limiting.
    
    Args:
        emails: List of dicts with keys: to_email, subject, body
        rate_limit: Emails per minute (default from config)
    
    Returns:
        List of (success, message) tuples
    """
    if rate_limit is None:
        rate_limit = EMAILS_PER_MINUTE
    
    delay_seconds = 60.0 / rate_limit
    results = []
    
    for i, email_data in enumerate(emails):
        # Check daily limit before each send
        if get_remaining_daily_quota() <= 0:
            results.append((False, "Daily email cap reached"))
            continue
        
        success, message = await send_email(
            to_email=email_data['to_email'],
            subject=email_data['subject'],
            body=email_data['body'],
            from_email=email_data.get('from_email'),
            from_name=email_data.get('from_name')
        )
        results.append((success, message))
        
        # Rate limiting delay (except for the last one)
        if i < len(emails) - 1:
            await asyncio.sleep(delay_seconds)
    
    return results


def test_gmail_connection() -> Tuple[bool, str]:
    """
    Test Gmail SMTP connection without sending an email.
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return False, "Gmail credentials not configured in .env"
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        return True, f"Successfully connected to Gmail as {GMAIL_ADDRESS}"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Check your Gmail address and app password."
    except Exception as e:
        return False, f"Connection error: {str(e)}"
