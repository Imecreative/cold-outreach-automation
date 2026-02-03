"""
Email Verification Providers Interface.
Supports multiple email verification services with fallback logic.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import httpx
import asyncio
from ..models import EmailVerificationStatus, VerificationResult


class EmailVerificationProvider(ABC):
    """Abstract base class for email verification providers."""
    
    @abstractmethod
    async def verify(self, email: str) -> VerificationResult:
        """Verify an email address."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get provider name."""
        pass


class TrumailProvider(EmailVerificationProvider):
    """Trumail API verification provider."""
    
    def __init__(self, api_url: str = "https://api.trumail.io/v2/lookups/json"):
        self.api_url = api_url
    
    async def verify(self, email: str) -> VerificationResult:
        """Verify email using Trumail API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {"email": email}
                response = await client.get(self.api_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Parse Trumail response
                    deliverable = data.get('deliverable', False)
                    full_inbox = data.get('fullInbox', False)
                    catch_all = data.get('catchAll', False)
                    
                    if deliverable and not full_inbox:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.VALID,
                            message="Trumail: Email is deliverable"
                        )
                    elif catch_all:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.CATCH_ALL,
                            message="Trumail: Domain is catch-all"
                        )
                    elif full_inbox:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.INVALID,
                            message="Trumail: Mailbox is full"
                        )
                    else:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.INVALID,
                            message="Trumail: Email not deliverable"
                        )
                else:
                    return VerificationResult(
                        email=email,
                        status=EmailVerificationStatus.UNKNOWN,
                        message=f"Trumail API error: {response.status_code}"
                    )
        except Exception as e:
            return VerificationResult(
                email=email,
                status=EmailVerificationStatus.UNKNOWN,
                message=f"Trumail error: {str(e)}"
            )
    
    def get_name(self) -> str:
        return "Trumail"


class HunterProvider(EmailVerificationProvider):
    """Hunter.io API verification provider."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.hunter.io/v2/email-verifier"
    
    async def verify(self, email: str) -> VerificationResult:
        """Verify email using Hunter.io API."""
        if not self.api_key:
            return VerificationResult(
                email=email,
                status=EmailVerificationStatus.UNKNOWN,
                message="Hunter.io: API key not configured"
            )
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "email": email,
                    "api_key": self.api_key
                }
                response = await client.get(self.api_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get('data', {})
                    
                    status_text = result.get('status', 'unknown')
                    score = result.get('score', 0)
                    
                    # Hunter returns: valid, invalid, accept_all, unknown, webmail, disposable, etc.
                    if status_text == 'valid' or score >= 80:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.VALID,
                            message=f"Hunter.io: Valid (score: {score})"
                        )
                    elif status_text == 'accept_all':
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.CATCH_ALL,
                            message="Hunter.io: Accept-all domain"
                        )
                    elif status_text == 'invalid' or score < 30:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.INVALID,
                            message=f"Hunter.io: Invalid (score: {score})"
                        )
                    else:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.UNKNOWN,
                            message=f"Hunter.io: {status_text} (score: {score})"
                        )
                elif response.status_code == 401:
                    return VerificationResult(
                        email=email,
                        status=EmailVerificationStatus.UNKNOWN,
                        message="Hunter.io: Invalid API key"
                    )
                else:
                    return VerificationResult(
                        email=email,
                        status=EmailVerificationStatus.UNKNOWN,
                        message=f"Hunter.io API error: {response.status_code}"
                    )
        except Exception as e:
            return VerificationResult(
                email=email,
                status=EmailVerificationStatus.UNKNOWN,
                message=f"Hunter.io error: {str(e)}"
            )
    
    def get_name(self) -> str:
        return "Hunter.io"


class KickboxProvider(EmailVerificationProvider):
    """Kickbox API verification provider."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://api.kickbox.com/v2/verify"
    
    async def verify(self, email: str) -> VerificationResult:
        """Verify email using Kickbox API."""
        if not self.api_key:
            return VerificationResult(
                email=email,
                status=EmailVerificationStatus.UNKNOWN,
                message="Kickbox: API key not configured"
            )
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "email": email,
                    "apikey": self.api_key
                }
                response = await client.get(self.api_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    result_status = data.get('result', 'unknown')
                    reason = data.get('reason', '')
                    
                    # Kickbox returns: deliverable, undeliverable, risky, unknown
                    if result_status == 'deliverable':
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.VALID,
                            message=f"Kickbox: Deliverable ({reason})"
                        )
                    elif result_status == 'undeliverable':
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.INVALID,
                            message=f"Kickbox: Undeliverable ({reason})"
                        )
                    elif result_status == 'risky' and reason == 'accept_all':
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.CATCH_ALL,
                            message="Kickbox: Risky - Accept-all domain"
                        )
                    else:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.UNKNOWN,
                            message=f"Kickbox: {result_status} ({reason})"
                        )
                else:
                    return VerificationResult(
                        email=email,
                        status=EmailVerificationStatus.UNKNOWN,
                        message=f"Kickbox API error: {response.status_code}"
                    )
        except Exception as e:
            return VerificationResult(
                email=email,
                status=EmailVerificationStatus.UNKNOWN,
                message=f"Kickbox error: {str(e)}"
            )
    
    def get_name(self) -> str:
        return "Kickbox"


class AbstractAPIProvider(EmailVerificationProvider):
    """AbstractAPI email validation provider."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://emailvalidation.abstractapi.com/v1/"
    
    async def verify(self, email: str) -> VerificationResult:
        """Verify email using AbstractAPI."""
        if not self.api_key:
            return VerificationResult(
                email=email,
                status=EmailVerificationStatus.UNKNOWN,
                message="AbstractAPI: API key not configured"
            )
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {
                    "api_key": self.api_key,
                    "email": email
                }
                response = await client.get(self.api_url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    is_valid_format = data.get('is_valid_format', {}).get('value', False)
                    is_smtp_valid = data.get('is_smtp_valid', {}).get('value', False)
                    is_catchall = data.get('is_catchall_email', {}).get('value', False)
                    deliverability = data.get('deliverability', 'UNKNOWN')
                    
                    if deliverability == 'DELIVERABLE' and is_valid_format and is_smtp_valid:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.VALID,
                            message="AbstractAPI: Deliverable"
                        )
                    elif is_catchall:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.CATCH_ALL,
                            message="AbstractAPI: Catch-all domain"
                        )
                    elif deliverability == 'UNDELIVERABLE':
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.INVALID,
                            message="AbstractAPI: Undeliverable"
                        )
                    else:
                        return VerificationResult(
                            email=email,
                            status=EmailVerificationStatus.UNKNOWN,
                            message=f"AbstractAPI: {deliverability}"
                        )
                else:
                    return VerificationResult(
                        email=email,
                        status=EmailVerificationStatus.UNKNOWN,
                        message=f"AbstractAPI error: {response.status_code}"
                    )
        except Exception as e:
            return VerificationResult(
                email=email,
                status=EmailVerificationStatus.UNKNOWN,
                message=f"AbstractAPI error: {str(e)}"
            )
    
    def get_name(self) -> str:
        return "AbstractAPI"
