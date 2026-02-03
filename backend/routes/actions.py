"""
Action routes for verification, scanning, drafting, and sending.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional, List
from datetime import datetime
import json
from pathlib import Path

from ..models import BulkActionRequest, EmailVerificationStatus, SequenceStep
from ..modules.excel_handler import get_handler
from ..modules.smtp_verifier import verify_email, smart_verify_email
from ..modules.website_scanner import scan_website
from ..modules.ai_drafter import generate_initial_draft, generate_followup_draft, generate_reply_draft
from ..modules.gmail_sender import send_email, get_remaining_daily_quota
from ..modules.scheduler import email_scheduler
from ..modules.time_utils import get_next_send_time
from ..config import (
    EMAIL_VERIFICATION_STRATEGY,
    HUNTER_API_KEY,    KICKBOX_API_KEY,
    ABSTRACT_API_KEY
)


router = APIRouter(prefix="/api", tags=["actions"])


# Progress tracking for bulk operations
_operation_progress = {
    "verify": {"running": False, "total": 0, "completed": 0, "current": "", "errors": []},
    "scan": {"running": False, "total": 0, "completed": 0, "current": "", "errors": []},
    "draft": {"running": False, "total": 0, "completed": 0, "current": "", "errors": []}
}


def get_progress(operation: str) -> dict:
    return _operation_progress.get(operation, {})


def _calculate_audit_score(tech: dict, content: dict) -> int:
    """Calculate overall audit score from technical and content data."""
    # SEO Score (0-100)
    seo_score = 0
    if tech.get('title'):
        seo_score += 20
    if tech.get('meta_description'):
        seo_score += 20
    if tech.get('h1'):
        seo_score += 15
    if tech.get('has_viewport_meta'):
        seo_score += 25
    if tech.get('ssl_enabled'):
        seo_score += 10
    if tech.get('has_structured_data'):
        seo_score += 10
    
    # Content Score (0-100)
    content_score = 0
    max_per_item = 100 // 6  # 6 key content elements
    if content.get('has_projects'):
        content_score += max_per_item
    if content.get('has_testimonials'):
        content_score += max_per_item
    if content.get('has_license'):
        content_score += max_per_item
    if content.get('has_about'):
        content_score += max_per_item
    if content.get('has_services'):
        content_score += max_per_item
    if content.get('has_social_links'):
        content_score += max_per_item
    
    # Overall score (average of both)
    overall_score = int((seo_score + min(content_score, 100)) / 2)
    return overall_score


@router.get("/progress/{operation}")
async def get_operation_progress(operation: str):
    """Get progress of a bulk operation."""
    if operation not in _operation_progress:
        raise HTTPException(status_code=400, detail="Invalid operation")
    return _operation_progress[operation]


@router.post("/verify")
async def verify_emails(request: BulkActionRequest, background_tasks: BackgroundTasks):
    """
    Verify emails for all or selected leads.
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded.")
    
    if _operation_progress["verify"]["running"]:
        raise HTTPException(status_code=409, detail="Verification already in progress")
    
    # Get leads
    if request.lead_ids:
        leads = [l for l in handler.leads if l.id in request.lead_ids]
    else:
        leads = handler.leads
    
    # Filter to only those with emails AND status is PENDING
    leads_to_verify = [l for l in leads if l.email and l.email_verified == EmailVerificationStatus.PENDING]
    
    if not leads_to_verify:
        return {"message": "No pending emails to verify", "count": 0}
    
    # Start background verification
    async def run_verification():
        import asyncio
        from ..config import VERIFIER_DELAY_SECONDS
        
        _operation_progress["verify"] = {
            "running": True, "total": len(leads_to_verify), 
            "completed": 0, "current": "", "errors": []
        }
        
        # Cache results for this run to avoid re-verifying the same email multiple times
        verification_cache = {}
        
        for lead in leads_to_verify:
            if not _operation_progress["verify"]["running"]: # Stop mechanism
                break
                
            _operation_progress["verify"]["current"] = lead.email
            
            try:
                # Check cache first
                if lead.email in verification_cache:
                    result_status = verification_cache[lead.email]
                else:
                    # Use smart verification with configured providers
                    result = await smart_verify_email(
                        lead.email,
                        strategy=EMAIL_VERIFICATION_STRATEGY,
                        hunter_api_key=HUNTER_API_KEY if HUNTER_API_KEY else None,
                        kickbox_api_key=KICKBOX_API_KEY if KICKBOX_API_KEY else None,
                        abstract_api_key=ABSTRACT_API_KEY if ABSTRACT_API_KEY else None
                    )
                    result_status = result.status
                    verification_cache[lead.email] = result_status
                    # Small delay to avoid hitting rate limits
                    await asyncio.sleep(VERIFIER_DELAY_SECONDS)
                
                handler.update_lead(lead.id, {
                    "email_verified": result_status,
                    "verification_checked_at": datetime.now()
                })
            except Exception as e:
                _operation_progress["verify"]["errors"].append(f"{lead.email}: {str(e)}")
            
            _operation_progress["verify"]["completed"] += 1
            
            # Periodically save (every 10 leads)
            if _operation_progress["verify"]["completed"] % 10 == 0:
                try:
                    handler.save()
                except:
                    pass
        
        # Final save
        try:
            handler.save()
        except:
            pass
        
        _operation_progress["verify"]["running"] = False
        _operation_progress["verify"]["current"] = ""
    
    background_tasks.add_task(run_verification)
    
    return {
        "message": f"Started verification for {len(leads_to_verify)} leads",
        "count": len(leads_to_verify)
    }


@router.post("/scan")
async def scan_websites(request: BulkActionRequest, background_tasks: BackgroundTasks):
    """
    Scan websites for all or selected leads.
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded.")
    
    if _operation_progress["scan"]["running"]:
        raise HTTPException(status_code=409, detail="Scanning already in progress")
    
    # Get leads to scan
    if request.lead_ids:
        leads = [l for l in handler.leads if l.id in request.lead_ids]
    else:
        leads = handler.leads
    
    # Filter to only those with websites
    leads_to_scan = [l for l in leads if l.website]
    
    if not leads_to_scan:
        return {"message": "No leads with websites to scan", "count": 0}
    
    # Start background scanning
    async def run_scanning():
        _operation_progress["scan"] = {
            "running": True, "total": len(leads_to_scan),
            "completed": 0, "current": "", "errors": []
        }
        
        for lead in leads_to_scan:
            _operation_progress["scan"]["current"] = lead.website
            
            try:
                result = await scan_website(lead.website)
                
                # Extract decision makers
                decision_makers = result.audit_data.get('decision_makers', []) if result.audit_data else []
                
                # Select primary owner name from decision makers
                owner_name = None
                decision_maker_names = []
                if decision_makers:
                    # Sort by confidence (already done in scanner, but ensure it)
                    sorted_makers = sorted(decision_makers, key=lambda x: x.get('confidence', 0), reverse=True)
                    if sorted_makers:
                        owner_name = sorted_makers[0]['name']
                    decision_maker_names = [dm['name'] for dm in sorted_makers[:5]]
                
                # Calculate audit score from audit data
                audit_score = None
                if result.audit_data:
                    tech = result.audit_data.get('technical', {})
                    content = result.audit_data.get('content', {})
                    audit_score = _calculate_audit_score(tech, content)
                
                # Get audit report paths
                audit_report_path = None
                if result.audit_report_paths:
                    # Store JSON path as primary, but keep reference to PDF
                    audit_report_path = result.audit_report_paths.get('json', '')
                
                # Update lead with enriched data
                update_data = {
                    "website_scan_summary": result.summary,
                    "website_scan_at": datetime.now(),
                }
                
                # Add owner name if found
                if owner_name:
                    update_data["owner_name"] = owner_name
                
                # Add audit score
                if audit_score is not None:
                    update_data["audit_score"] = audit_score
                
                # Add audit report path
                if audit_report_path:
                    update_data["audit_report_path"] = audit_report_path
                
                # Add decision makers list
                if decision_maker_names:
                    update_data["decision_makers"] = decision_maker_names
                
                handler.update_lead(lead.id, update_data)
                
            except Exception as e:
                _operation_progress["scan"]["errors"].append(f"{lead.website}: {str(e)}")
            
            _operation_progress["scan"]["completed"] += 1
            
            # Periodically save (every 5 scans)
            if _operation_progress["scan"]["completed"] % 5 == 0:
                try:
                    handler.save()
                except:
                    pass
        
        # Save changes
        try:
            handler.save()
        except:
            pass
        
        _operation_progress["scan"]["running"] = False
        _operation_progress["scan"]["current"] = ""
    
    background_tasks.add_task(run_scanning)
    
    return {
        "message": f"Started scanning for {len(leads_to_scan)} leads",
        "count": len(leads_to_scan)
    }


@router.post("/leads/{lead_id}/generate-draft")
async def generate_draft(lead_id: int, draft_type: str = "initial"):
    """
    Generate an AI draft for a specific lead.
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded.")
    
    lead = handler.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found")
    
    try:
        if draft_type == "initial":
            # Try to load audit data if available
            audit_data = None
            if hasattr(lead, 'audit_report_path') and lead.audit_report_path:
                try:
                    audit_report_path = Path(lead.audit_report_path)
                    if audit_report_path.exists():
                        with open(audit_report_path, 'r', encoding='utf-8') as f:
                            report = json.load(f)
                            audit_data = {
                                'technical': report.get('technical_seo', {}),
                                'content': report.get('content_analysis', {}),
                                'decision_makers': report.get('decision_makers', [])
                            }
                except Exception as e:
                    print(f"Could not load audit data: {e}")
            
            draft = generate_initial_draft(
                lead, 
                scan_summary=lead.website_scan_summary,
                notes=lead.my_notes,
                audit_data=audit_data
            )
        elif draft_type == "followup":
            # Determine which followup number based on current sequence step
            if lead.sequence_step == SequenceStep.INITIAL_SENT:
                followup_num = 1
            elif lead.sequence_step == SequenceStep.GHOST_1_SENT:
                followup_num = 2
            else:
                followup_num = 1
            draft = generate_followup_draft(lead, followup_num)
        elif draft_type == "reply":
            if not lead.their_last_reply:
                raise HTTPException(status_code=400, detail="No reply to respond to. Add their reply first.")
            draft = generate_reply_draft(lead, lead.their_last_reply)
        else:
            raise HTTPException(status_code=400, detail="Invalid draft_type. Use: initial, followup, or reply")
        
        # Update lead with draft
        handler.update_lead(lead_id, {
            "email_subject": draft.subject,
            "email_draft": draft.body
        })
        
        # Save changes
        try:
            handler.save()
        except:
            pass
        
        return {
            "lead_id": lead_id,
            "subject": draft.subject,
            "body": draft.body
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate draft: {str(e)}")


@router.post("/generate-drafts")
async def generate_drafts_bulk(request: BulkActionRequest, background_tasks: BackgroundTasks):
    """
    Generate drafts for all or selected leads.
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded.")
    
    if _operation_progress["draft"]["running"]:
        raise HTTPException(status_code=409, detail="Draft generation already in progress")
    
    # Get leads
    if request.lead_ids:
        leads = [l for l in handler.leads if l.id in request.lead_ids]
    else:
        leads = handler.leads
    
    # Filter to only those without drafts and with valid emails
    leads_to_draft = [l for l in leads if not l.email_draft and 
                      l.email_verified != EmailVerificationStatus.INVALID]
    
    if not leads_to_draft:
        return {"message": "No leads need drafts", "count": 0}
    
    # Start background draft generation
    async def run_drafting():
        _operation_progress["draft"] = {
            "running": True, "total": len(leads_to_draft),
            "completed": 0, "current": "", "errors": []
        }
        
        for lead in leads_to_draft:
            _operation_progress["draft"]["current"] = lead.name or lead.email
            
            try:
                # Try to load audit data if available
                audit_data = None
                if hasattr(lead, 'audit_report_path') and lead.audit_report_path:
                    try:
                        audit_report_path = Path(lead.audit_report_path)
                        if audit_report_path.exists():
                            with open(audit_report_path, 'r', encoding='utf-8') as f:
                                report = json.load(f)
                                audit_data = {
                                    'technical': report.get('technical_seo', {}),
                                    'content': report.get('content_analysis', {}),
                                    'decision_makers': report.get('decision_makers', [])
                                }
                    except Exception as e:
                        print(f"Could not load audit data for {lead.name}: {e}")
                
                draft = generate_initial_draft(
                    lead,
                    scan_summary=lead.website_scan_summary,
                    notes=lead.my_notes,
                    audit_data=audit_data
                )
                handler.update_lead(lead.id, {
                    "email_subject": draft.subject,
                    "email_draft": draft.body
                })
            except Exception as e:
                _operation_progress["draft"]["errors"].append(f"{lead.email}: {str(e)}")
            
            _operation_progress["draft"]["completed"] += 1
        
        # Save changes
        try:
            handler.save()
        except:
            pass
        
        _operation_progress["draft"]["running"] = False
        _operation_progress["draft"]["current"] = ""
    
    background_tasks.add_task(run_drafting)
    
    return {
        "message": f"Started draft generation for {len(leads_to_draft)} leads",
        "count": len(leads_to_draft)
    }


@router.post("/leads/{lead_id}/send")
async def send_lead_email(
    lead_id: int, 
    subject: Optional[str] = None, 
    body: Optional[str] = None
):
    """
    Send email to a specific lead.
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded.")
    
    lead = handler.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found")
    
    # Check daily quota
    if get_remaining_daily_quota() <= 0:
        raise HTTPException(status_code=429, detail="Daily email quota reached")
    
    # Use provided or lead's draft
    email_subject = subject or lead.email_subject
    email_body = body or lead.email_draft
    
    if not email_subject or not email_body:
        raise HTTPException(status_code=400, detail="No email draft. Generate a draft first.")
    
    if not lead.email:
        raise HTTPException(status_code=400, detail="Lead has no email address")
    
    # Send email
    success, message = await send_email(
        to_email=lead.email,
        subject=email_subject,
        body=email_body
    )
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {message}")
    
    # Update lead status
    new_step = SequenceStep.INITIAL_SENT
    if lead.sequence_step == SequenceStep.INITIAL_SENT:
        new_step = SequenceStep.GHOST_1_SENT
    elif lead.sequence_step == SequenceStep.GHOST_1_SENT:
        new_step = SequenceStep.GHOST_2_SENT
    
    handler.update_lead(lead_id, {
        "email_sent_at": datetime.now(),
        "sequence_step": new_step,
        "email_subject": email_subject,
        "email_draft": email_body
    })
    
    # Save changes
    try:
        handler.save()
    except:
        pass
    
    return {
        "success": True,
        "message": message,
        "lead_id": lead_id,
        "sequence_step": new_step.value
    }


from pydantic import BaseModel

class ScheduleEmailRequest(BaseModel):
    send_at: Optional[datetime] = None
    subject: Optional[str] = None
    body: Optional[str] = None


@router.post("/leads/{lead_id}/schedule")
async def schedule_email_endpoint(lead_id: int, request: Optional[ScheduleEmailRequest] = None):
    """
    Schedule an email for a lead.
    If send_at is not provided, calculates optimal time based on timezone.
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded.")
    
    lead = handler.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found")
        
    # Get parameters
    req = request or ScheduleEmailRequest()
    subject = req.subject or lead.email_subject
    body = req.body or lead.email_draft
    send_at = req.send_at
    
    if not subject or not body:
         raise HTTPException(status_code=400, detail="No email draft. Generate a draft first or provide in request.")
    
    # Calculate time if needed
    if not send_at:
        send_at = get_next_send_time(lead.city)
    
    # If naive, assume server time (or default logic in scheduler)
    # APScheduler handles naive datetimes as local time by default.

    try:
        job_id = email_scheduler.schedule_email(lead_id, subject, body, send_at)
        
        # Update lead
        handler.update_lead(lead_id, {
            "scheduled_at": send_at,
            "email_subject": subject,
            "email_draft": body
        })
        # Save happens in update_lead usually? No, explicit save needed in this codebase pattern
        try:
            handler.save()
        except:
            pass
        
        return {
            "success": True,
            "lead_id": lead_id,
            "scheduled_at": send_at.isoformat(),
            "job_id": job_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule email: {str(e)}")


@router.post("/leads/{lead_id}/cancel-schedule")
async def cancel_schedule_endpoint(lead_id: int):
    """Cancel a scheduled email."""
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded.")
        
    try:
        success = email_scheduler.cancel_email(lead_id)
        
        # Always clear status even if job not found (might be out of sync)
        try:
            handler.update_lead(lead_id, {
                "scheduled_at": None
            })
            handler.save()
        except:
            pass
            
        if success:
             return {"success": True, "message": "Email schedule cancelled"}
        else:
            return {"success": True, "message": "Schedule cleared (job was not found)"}
            
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to cancel schedule: {str(e)}")
