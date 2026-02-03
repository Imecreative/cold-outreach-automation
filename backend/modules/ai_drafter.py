"""
AI Draft Generator Module.
Placeholder for AI-powered email draft generation.
Ready for future integration with Claude/Anthropic APIs.
"""

from typing import Optional, Dict, Any, List
from ..models import Lead, EmailDraft


# Consultant voice template for mock drafts
INITIAL_EMAIL_TEMPLATE = """Hi {owner_name},

I came across {company_context} and noticed a few things about your website that could be helping you connect with more serious homeowners.

{personalized_observations}

A solid website does the heavy lifting for you—showing your licenses, building trust, and making it easy for the right clients to reach out.

Would you be open to a quick call this week to chat about it?

Best,
[Your Name]"""


GHOST_FOLLOWUP_TEMPLATE = """Hi {owner_name},

Just wanted to follow up on my last email. I know you're busy, but I really think there's a quick win here for {website}.

{brief_reminder}

Let me know if you'd like to connect.

Best,
[Your Name]"""


REPLY_TEMPLATE = """Hi {owner_name},

Thanks for getting back to me!

{contextual_response}

I'm happy to hop on a quick call whenever works for you. What does your schedule look like this week?

Best,
[Your Name]"""


def generate_initial_draft(lead: Lead, scan_summary: Optional[str] = None, notes: Optional[str] = None, audit_data: Optional[Dict[str, Any]] = None) -> EmailDraft:
    """
    Generate an initial cold email draft with personalized content based on audit data.
    
    Args:
        lead: Lead data
        scan_summary: Website scan summary (deprecated, use audit_data)
        notes: Manual notes
        audit_data: Full audit data from website scan (preferred)
    """
    # Extract dynamic variables
    owner_name = lead.owner_name or lead.name or "there"
    first_name = owner_name.split()[0] if ' ' in owner_name else owner_name
    company_name = lead.name or "your business"
    city = lead.city or ""
    category = lead.category or "contractor"
    audit_score = lead.audit_score if hasattr(lead, 'audit_score') else None
    
    # Build company context
    if lead.category and lead.city:
        company_context = f"your {lead.category.lower()} business in {lead.city}"
    elif lead.category:
        company_context = f"your {lead.category.lower()} business"
    elif lead.website:
        company_context = f"{lead.website}"
    else:
        company_context = "your business"
    
    # Build personalized observations using audit data
    observations = _extract_observations_from_audit(audit_data, scan_summary, audit_score)
    
    # Add manual notes if provided
    if notes:
        observations.insert(0, notes)
    
    # Limit to top 3 most impactful observations
    observations = observations[:3]
    
    # Format observations
    if observations:
        personalized_observations = "\n\n".join(f"• {obs}" for obs in observations)
    else:
        personalized_observations = "• A few tweaks to the layout and messaging could help showcase your expertise and build trust with potential clients."
    
    # Generate email body with dynamic variables
    body = INITIAL_EMAIL_TEMPLATE.format(
        owner_name=first_name,
        company_context=company_context,
        personalized_observations=personalized_observations
    )
    
    # Generate personalized subject line
    subject = _generate_subject_line(lead, audit_score)
    
    return EmailDraft(subject=subject, body=body)


def _extract_observations_from_audit(audit_data: Optional[Dict[str, Any]], scan_summary: Optional[str], audit_score: Optional[int]) -> List[str]:
    """
    Extract specific, actionable observations from audit data.
    Prioritizes high-impact issues.
    """
    observations = []
    
    if not audit_data:
        # Fallback to parsing scan summary if audit data not available
        if scan_summary:
            return _parse_scan_summary(scan_summary)
        return []
    
    tech = audit_data.get('technical', {})
    content = audit_data.get('content', {})
    
    # High Priority: Mobile Responsiveness (60% of traffic)
    if not tech.get('has_viewport_meta'):
        observations.append(
            "Your site isn't mobile-friendly. Since 60% of homeowners browse on their phones, "
            "you're likely losing qualified leads before they even see your work."
        )
    
    # High Priority: Missing License Info (trust factor)
    if not content.get('has_license'):
        observations.append(
            "I noticed your licensing information isn't prominently displayed. "
            "In my experience, homeowners specifically look for this when choosing contractors—it's a major trust factor."
        )
    
    # High Priority: No SSL (security concern)
    if tech.get('ssl_enabled') == False:
        observations.append(
            "Your site doesn't have an SSL certificate (https). Modern browsers flag this as 'Not Secure,' "
            "which immediately puts homeowners on guard."
        )
    
    # Medium Priority: Missing Portfolio/Projects
    if not content.get('has_projects'):
        observations.append(
            "You don't have a portfolio showcasing your projects. Visual proof of quality work "
            "is one of the most powerful tools for converting visitors into leads."
        )
    
    # Medium Priority: No Testimonials
    if not content.get('has_testimonials'):
        observations.append(
            "There are no customer testimonials or reviews visible on your site. "
            "Social proof is critical—homeowners want to see that others trust you."
        )
    
    # Medium Priority: SEO Issues
    if not tech.get('title') or not tech.get('meta_description'):
        observations.append(
            "Your site is missing key SEO elements (title tags, meta descriptions). "
            "This makes it much harder for homeowners to find you when searching for contractors in your area."
        )
    
    # Low Priority: Platform-specific insights
    platform = tech.get('platform', '')
    if platform == 'WordPress':
        if not tech.get('has_viewport_meta') or not content.get('has_projects'):
            observations.append(
                "I see you're on WordPress—great platform for flexibility. "
                "With a few plugin updates and template tweaks, we could showcase your work much more effectively."
            )
    elif platform == 'Wix' or platform == 'Squarespace':
        observations.append(
            f"You're using {platform}, which is convenient but can be limiting for contractors. "
            "There are some quick customizations that could help you stand out and rank better locally."
        )
    
    # Add score-based observation if available
    if audit_score is not None:
        if audit_score < 60:
            observations.insert(0, 
                f"Your website scored {audit_score}/100 in my technical audit. "
                "There are some quick wins that could dramatically improve how homeowners see your business online."
            )
        elif audit_score < 80:
            observations.append(
                f"Your site scored {audit_score}/100—not bad, but there's real opportunity to stand out from competitors "
                "with a few strategic improvements."
            )
    
    return observations


def _parse_scan_summary(scan_summary: str) -> List[str]:
    """
    Fallback method: Parse scan summary for issues (legacy support).
    """
    observations = []
    scan_lower = scan_summary.lower()
    
    if "not mobile responsive" in scan_lower or "no viewport" in scan_lower:
        observations.append(
            "Your site isn't mobile-friendly, which means you're losing 60% of potential customers "
            "who browse on their phones."
        )
    
    if "missing title" in scan_lower or "missing meta" in scan_lower:
        observations.append(
            "Your site is missing critical SEO elements. This makes it harder for homeowners "
            "to find you when searching for contractors in your area."
        )
    
    if "no projects" in scan_lower or "no portfolio" in scan_lower:
        observations.append(
            "I don't see a portfolio of your work. Visual proof is one of the most powerful "
            "tools for converting visitors into paying customers."
        )
    
    if "no testimonials" in scan_lower:
        observations.append(
            "You're missing customer testimonials. Homeowners want to see that others trust you "
            "before they reach out."
        )
    
    if "no ssl" in scan_lower:
        observations.append(
            "Your site doesn't have SSL (https), which browsers flag as 'Not Secure.' "
            "This immediately puts homeowners on guard."
        )
    
    if not observations:
        observations.append(
            "A few strategic improvements to your website could help you attract more qualified leads "
            "and stand out from competitors."
        )
    
    return observations


def _generate_subject_line(lead: Lead, audit_score: Optional[int]) -> str:
    """
    Generate a personalized subject line using lead data and audit score.
    """
    city = lead.city
    category = lead.category
    
    # Personalized subject lines based on available data
    if audit_score and audit_score < 60:
        if city:
            return f"Quick wins for your {city} website"
        return "I found some quick wins for your website"
    
    if city and category:
        return f"Thought about your {category.lower()} site in {city}"
    elif city:
        return f"Quick idea for your {city} website"
    elif category:
        return f"Idea for your {category.lower()} website"
    else:
        return "Quick thought about your website"


def generate_followup_draft(lead: Lead, followup_number: int = 1) -> EmailDraft:
    """
    Generate a ghost follow-up email draft.
    """
    owner_name = lead.owner_name or lead.name or "there"
    first_name = owner_name.split()[0] if ' ' in owner_name else owner_name
    
    website = lead.website or "your site"
    
    if followup_number == 1:
        brief_reminder = "I noticed a couple of things that could help you stand out to homeowners looking for reliable contractors."
        subject = f"Following up - {website}"
    else:
        brief_reminder = "Just a gentle bump on my earlier email. Happy to share some ideas whenever you have a moment."
        subject = f"Still interested in connecting?"
    
    body = GHOST_FOLLOWUP_TEMPLATE.format(
        owner_name=first_name,
        website=website,
        brief_reminder=brief_reminder
    )
    
    return EmailDraft(subject=subject, body=body)


def generate_reply_draft(lead: Lead, their_reply: str) -> EmailDraft:
    """
    Generate a reply to the lead's response.
    """
    owner_name = lead.owner_name or lead.name or "there"
    first_name = owner_name.split()[0] if ' ' in owner_name else owner_name
    
    # Simple contextual response based on common reply patterns
    reply_lower = their_reply.lower()
    
    if any(word in reply_lower for word in ['interested', 'tell me more', 'curious', 'sounds good']):
        contextual_response = "Great to hear you're interested! Based on what I saw on your site, I think we could make some impactful improvements that would help you attract more qualified leads from homeowners in your area."
    elif any(word in reply_lower for word in ['busy', 'not right now', 'maybe later']):
        contextual_response = "Totally understand—timing is everything. I'll keep this brief: when you're ready to look at the website, I'd be happy to walk you through a few quick ideas that won't take much of your time."
    elif any(word in reply_lower for word in ['cost', 'price', 'how much', 'budget']):
        contextual_response = "Great question! The investment really depends on what you're looking to achieve. I'd love to understand your goals first so I can give you an accurate picture."
    elif any(word in reply_lower for word in ['who are you', 'company', 'about you']):
        contextual_response = "Happy to share! I help home improvement contractors build websites that actually convert visitors into qualified leads. The focus is on showing your expertise and building trust with homeowners."
    else:
        contextual_response = "I appreciate you getting back to me. I'd love to learn more about what you're looking for and see if there's a way I can help."
    
    body = REPLY_TEMPLATE.format(
        owner_name=first_name,
        contextual_response=contextual_response
    )
    
    subject = f"Re: {lead.email_subject or 'Your website'}"
    
    return EmailDraft(subject=subject, body=body)


# Future AI integration placeholder
async def generate_draft_with_ai(
    lead: Lead,
    draft_type: str = "initial",
    scan_summary: Optional[str] = None,
    notes: Optional[str] = None,
    their_reply: Optional[str] = None,
    api_key: Optional[str] = None
) -> EmailDraft:
    """
    Generate a draft using AI API.
    
    This is a placeholder that currently falls back to template-based generation.
    When AI integration is ready, this will call the appropriate API.
    
    Args:
        lead: Lead data
        draft_type: "initial", "followup", or "reply"
        scan_summary: Website scan summary
        notes: Manual notes
        their_reply: Their reply (for reply drafts)
        api_key: AI API key (for future use)
    
    Returns:
        EmailDraft with subject and body
    """
    # TODO: Implement actual AI API integration
    # For now, use template-based generation
    
    if draft_type == "initial":
        return generate_initial_draft(lead, scan_summary, notes)
    elif draft_type == "followup":
        return generate_followup_draft(lead)
    elif draft_type == "reply" and their_reply:
        return generate_reply_draft(lead, their_reply)
    else:
        return generate_initial_draft(lead, scan_summary, notes)
