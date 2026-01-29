"""
Lead CRUD routes.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from ..models import Lead, LeadUpdate, EmailVerificationStatus, SequenceStep
from ..modules.excel_handler import get_handler


router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("", response_model=dict)
async def list_leads(
    email_verified: Optional[str] = Query(None, description="Filter by verification status"),
    has_draft: Optional[bool] = Query(None, description="Filter by has draft"),
    sequence_step: Optional[str] = Query(None, description="Filter by sequence step"),
    has_scan: Optional[bool] = Query(None, description="Filter by has website scan"),
    search: Optional[str] = Query(None, description="Search in name, email, website"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=10, le=500, description="Items per page")
):
    """
    List all leads with optional filters and pagination.
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded. Upload a file first.")
    
    leads = handler.leads
    
    # Apply filters
    if email_verified:
        try:
            status = EmailVerificationStatus(email_verified.lower())
            leads = [l for l in leads if l.email_verified == status]
        except ValueError:
            pass
    
    if has_draft is not None:
        if has_draft:
            leads = [l for l in leads if l.email_draft]
        else:
            leads = [l for l in leads if not l.email_draft]
    
    if sequence_step:
        try:
            step = SequenceStep(sequence_step.lower())
            leads = [l for l in leads if l.sequence_step == step]
        except ValueError:
            pass
    
    if has_scan is not None:
        if has_scan:
            leads = [l for l in leads if l.website_scan_summary]
        else:
            leads = [l for l in leads if not l.website_scan_summary]
    
    if search:
        search_lower = search.lower()
        leads = [l for l in leads if 
                 search_lower in (l.name or '').lower() or
                 search_lower in (l.email or '').lower() or
                 search_lower in (l.website or '').lower()]
    
    # Pagination
    total = len(leads)
    total_pages = (total + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_leads = leads[start_idx:end_idx]
    
    # Convert to dicts for response
    return {
        "leads": [lead.model_dump() for lead in paginated_leads],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }


@router.get("/{lead_id}", response_model=dict)
async def get_lead(lead_id: int):
    """
    Get a single lead by ID.
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded.")
    
    lead = handler.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found")
    
    return lead.model_dump()


@router.put("/{lead_id}", response_model=dict)
async def update_lead(lead_id: int, update: LeadUpdate):
    """
    Update a lead's editable fields (notes, draft, etc.)
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded.")
    
    # Build update dict from non-None values
    update_dict = {k: v for k, v in update.model_dump().items() if v is not None}
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    lead = handler.update_lead(lead_id, update_dict)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found")
    
    # Save changes to file
    try:
        handler.save()
    except Exception as e:
        pass  # Continue even if save fails, data is in memory
    
    return lead.model_dump()


@router.get("/stats/summary")
async def get_stats():
    """
    Get summary statistics about leads.
    """
    handler = get_handler()
    if not handler:
        return {
            "total": 0,
            "verified": {"valid": 0, "invalid": 0, "unknown": 0, "pending": 0},
            "drafts": {"has_draft": 0, "no_draft": 0},
            "scanned": {"scanned": 0, "not_scanned": 0},
            "sent": {"sent": 0, "not_sent": 0}
        }
    
    leads = handler.leads
    
    verified = {
        "valid": len([l for l in leads if l.email_verified == EmailVerificationStatus.VALID]),
        "invalid": len([l for l in leads if l.email_verified == EmailVerificationStatus.INVALID]),
        "unknown": len([l for l in leads if l.email_verified == EmailVerificationStatus.UNKNOWN]),
        "pending": len([l for l in leads if l.email_verified == EmailVerificationStatus.PENDING]),
        "catch_all": len([l for l in leads if l.email_verified == EmailVerificationStatus.CATCH_ALL])
    }
    
    drafts = {
        "has_draft": len([l for l in leads if l.email_draft]),
        "no_draft": len([l for l in leads if not l.email_draft])
    }
    
    scanned = {
        "scanned": len([l for l in leads if l.website_scan_summary]),
        "not_scanned": len([l for l in leads if not l.website_scan_summary])
    }
    
    sent = {
        "sent": len([l for l in leads if l.sequence_step != SequenceStep.NOT_SENT]),
        "not_sent": len([l for l in leads if l.sequence_step == SequenceStep.NOT_SENT])
    }
    
    return {
        "total": len(leads),
        "verified": verified,
        "drafts": drafts,
        "scanned": scanned,
        "sent": sent
    }
