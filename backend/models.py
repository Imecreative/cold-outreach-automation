"""
Pydantic models for the Cold Outreach Email Automation System.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum


class EmailVerificationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    CATCH_ALL = "catch-all"
    PENDING = "pending"


class ScheduledEmailStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class SequenceStep(str, Enum):
    NOT_SENT = "not_sent"
    INITIAL_SENT = "initial_sent"
    GHOST_1_SENT = "ghost_1_sent"
    GHOST_2_SENT = "ghost_2_sent"
    REPLIED = "replied"


class Lead(BaseModel):
    """Complete lead model with all fields"""
    id: int
    name: str
    email: str
    website: Optional[str] = None
    category: Optional[str] = None
    city: Optional[str] = None
    
    # New fields we add
    email_verified: EmailVerificationStatus = EmailVerificationStatus.PENDING
    verification_checked_at: Optional[datetime] = None
    website_scan_summary: Optional[str] = None
    website_scan_at: Optional[datetime] = None
    my_notes: Optional[str] = None
    email_draft: Optional[str] = None
    email_subject: Optional[str] = None
    email_sent_at: Optional[datetime] = None
    owner_name: Optional[str] = None
    sequence_step: SequenceStep = SequenceStep.NOT_SENT
    sequence_step: SequenceStep = SequenceStep.NOT_SENT
    their_last_reply: Optional[str] = None
    my_reply_draft: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    
    # Additional Excel columns (preserved)
    extra_data: dict = {}


class LeadUpdate(BaseModel):
    """Model for updating lead fields"""
    my_notes: Optional[str] = None
    email_draft: Optional[str] = None
    email_subject: Optional[str] = None
    owner_name: Optional[str] = None
    their_last_reply: Optional[str] = None
    my_reply_draft: Optional[str] = None


class LeadFilter(BaseModel):
    """Filter options for listing leads"""
    email_verified: Optional[EmailVerificationStatus] = None
    has_draft: Optional[bool] = None
    sequence_step: Optional[SequenceStep] = None
    has_scan: Optional[bool] = None


class VerificationResult(BaseModel):
    """Result from SMTP email verification"""
    email: str
    status: EmailVerificationStatus
    message: Optional[str] = None


class WebsiteScanResult(BaseModel):
    """Result from website scanning"""
    url: str
    title: Optional[str] = None
    meta_description: Optional[str] = None
    response_time_ms: Optional[int] = None
    platform: Optional[str] = None
    has_viewport_meta: bool = False
    audit_data: Optional[dict] = None
    summary: str


class EmailDraft(BaseModel):
    """Generated email draft"""
    subject: str
    body: str


class SendEmailRequest(BaseModel):
    """Request to send an email"""
    lead_id: int
    subject: Optional[str] = None  # Override draft subject
    body: Optional[str] = None  # Override draft body


class BulkActionRequest(BaseModel):
    """Request for bulk operations"""
    lead_ids: Optional[List[int]] = None  # None = all leads


class ActionProgress(BaseModel):
    """Progress update for bulk operations"""
    total: int
    completed: int
    current_item: Optional[str] = None
    errors: List[str] = []


class ScheduledEmail(BaseModel):
    """Model for a scheduled email job"""
    id: str
    lead_id: int
    subject: str
    body: str
    scheduled_time: datetime
    status: ScheduledEmailStatus = ScheduledEmailStatus.PENDING
    error: Optional[str] = None
    created_at: datetime = datetime.now()
