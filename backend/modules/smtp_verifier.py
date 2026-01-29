"""
SMTP Email Verifier Module.
Verifies email deliverability using SMTP protocol without sending actual emails.
"""

import dns.resolver
import smtplib
import socket
import asyncio
from typing import Tuple, List
from concurrent.futures import ThreadPoolExecutor
import time
from email_validator import validate_email, EmailNotValidError, EmailUndeliverableError

from ..config import VERIFIER_DELAY_SECONDS, VERIFIER_FROM_EMAIL
from ..models import EmailVerificationStatus, VerificationResult


# Thread pool for running blocking SMTP operations
_executor = ThreadPoolExecutor(max_workers=5)


def get_mx_records(domain: str) -> List[str]:
    """
    Get MX records for a domain.
    Returns list of mail servers sorted by priority.
    """
    try:
        records = dns.resolver.resolve(domain, 'MX')
        mx_hosts = [(record.preference, str(record.exchange).rstrip('.')) 
                    for record in records]
        mx_hosts.sort(key=lambda x: x[0])
        return [host for _, host in mx_hosts]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, 
            dns.resolver.NoNameservers, dns.exception.Timeout):
        return []


def _verify_email_sync(email: str, from_email: str = None) -> Tuple[EmailVerificationStatus, str]:
    """
    Synchronous SMTP verification.
    Connects to mail server and checks if recipient is valid.
    """
    if from_email is None:
        from_email = VERIFIER_FROM_EMAIL
    
    # 1. Syntax and Basic DNS check using email-validator
    try:
        # check_deliverability=True verifies domain and MX records
        v = validate_email(email, check_deliverability=True)
        # We'll use the normalized version
        email = v.email
        domain = v.domain
    except EmailNotValidError as e:
        return EmailVerificationStatus.INVALID, f"Syntax error: {str(e)}"
    except EmailUndeliverableError as e:
        return EmailVerificationStatus.INVALID, f"Domain error: {str(e)}"
    except Exception as e:
        # Other validation errors (likely network issues during DNS check)
        pass # Fallback to manual MX check below if DNS check failed here but might work manually
    
    # 2. Get MX records manually for better control
    local_part, domain = email.rsplit('@', 1)
    mx_hosts = get_mx_records(domain)
    
    if not mx_hosts:
        return EmailVerificationStatus.INVALID, f"No MX records found for domain {domain}"
    
    # 3. Try SMTP verification
    # We use a more realistic HELO/EHLO domain. Ideally this should be a real domain pointing to your IP.
    helo_domain = from_email.split('@')[-1] if '@' in from_email else 'gmail.com'
    
    last_error = ""
    for mx_host in mx_hosts[:2]:  # Try top 2 servers
        try:
            smtp = smtplib.SMTP(timeout=15)
            # Some servers require EHLO
            smtp.connect(mx_host, 25)
            smtp.ehlo(helo_domain)
            
            # Identify sender
            code, message = smtp.mail(from_email)
            if code != 250:
                smtp.quit()
                last_error = f"MAIL FROM rejected ({code}): {message}"
                continue
            
            # The actual recipient check
            code, message = smtp.rcpt(email)
            smtp.quit()
            
            if code == 250:
                return EmailVerificationStatus.VALID, "Mailbox exists"
            elif code == 550:
                return EmailVerificationStatus.INVALID, "Mailbox does not exist"
            elif code == 551 or code == 552 or code == 553 or code == 554:
                return EmailVerificationStatus.INVALID, f"Rejected ({code}): {message}"
            elif 400 <= code < 500:
                # Often Greylisting or Temporary block (common from residential IPs)
                return EmailVerificationStatus.UNKNOWN, f"Temporary/Rate limit block ({code})"
            else:
                last_error = f"Unexpected response ({code}): {message}"
                continue
                
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, 
                socket.timeout, socket.gaierror, ConnectionRefusedError) as e:
            last_error = f"Connection failed: {str(e)}"
            continue
        except Exception as e:
            last_error = f"System error: {str(e)}"
            continue
            
    # If we reached here, SMTP checks failed.
    # IMPORTANT: If the domain exists and MX records exist, but we can't connect,
    # it's likely our IP is being blocked, not that the email is invalid.
    # In cold outreach, we should treat these as "PROBABLY VALID" or UNKNOWN but not INVALID.
    return EmailVerificationStatus.UNKNOWN, f"Could not verify via SMTP: {last_error}"


async def verify_email(email: str, from_email: str = None) -> VerificationResult:
    """
    Async wrapper for email verification.
    Runs the synchronous SMTP check in a thread pool.
    """
    loop = asyncio.get_event_loop()
    status, message = await loop.run_in_executor(
        _executor, 
        _verify_email_sync, 
        email, 
        from_email
    )
    
    return VerificationResult(
        email=email,
        status=status,
        message=message
    )


async def verify_emails_batch(emails: list, delay: float = None) -> list:
    """
    Verify a batch of emails with delay between each.
    Returns list of VerificationResult objects.
    """
    if delay is None:
        delay = VERIFIER_DELAY_SECONDS
    
    results = []
    for i, email in enumerate(emails):
        result = await verify_email(email)
        results.append(result)
        
        # Add delay between verifications (except for the last one)
        if i < len(emails) - 1:
            await asyncio.sleep(delay)
    
    return results


def check_catch_all(domain: str, sample_size: int = 2) -> bool:
    """
    Check if a domain is a catch-all (accepts any email).
    Tests with random non-existent addresses.
    """
    import random
    import string
    
    valid_count = 0
    tried = 0
    
    for _ in range(sample_size):
        random_local = ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))
        test_email = f"{random_local}@{domain}"
        status, _ = _verify_email_sync(test_email)
        
        if status == EmailVerificationStatus.VALID:
            valid_count += 1
        
        tried += 1
        time.sleep(1.0)
    
    return tried > 0 and valid_count == tried
