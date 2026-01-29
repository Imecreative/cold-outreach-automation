"""
AI Draft Generator Module.
Placeholder for AI-powered email draft generation.
Ready for future integration with Claude/Anthropic APIs.
"""

from typing import Optional
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


def generate_initial_draft(lead: Lead, scan_summary: Optional[str] = None, notes: Optional[str] = None) -> EmailDraft:
    """
    Generate an initial cold email draft.
    Currently returns a mock template-based draft.
    
    In the future, this will call an AI API to generate personalized content.
    """
    owner_name = lead.owner_name or lead.name or "there"
    
    # Build company context
    if lead.category and lead.city:
        company_context = f"your {lead.category.lower()} business in {lead.city}"
    elif lead.category:
        company_context = f"your {lead.category.lower()} business"
    elif lead.website:
        company_context = f"{lead.website}"
    else:
        company_context = "your business"
    
    # Build personalized observations from scan and notes
    observations = []
    
    if scan_summary:
        # Parse scan summary for specific issues
        scan_lower = scan_summary.lower()
        if "slow" in scan_lower:
            observations.append("Your site seems to load a bit slowly, which can turn away potential customers before they even see your work.")
        if "no meta description" in scan_lower:
            observations.append("The site could use some SEO improvements to help homeowners find you more easily on Google.")
        if "not be mobile-friendly" in scan_lower:
            observations.append("It looks like the site might not be fully optimized for mobile, which is where most homeowners browse these days.")
        if "wordpress" in scan_lower.lower():
            observations.append("I see you're using WordPress—great choice for flexibility, but it might need some performance tuning.")
    
    if notes:
        observations.append(notes)
    
    if not observations:
        observations.append("A few tweaks to the layout and messaging could help showcase your expertise and build trust with potential clients.")
    
    personalized_observations = "\n\n".join(f"• {obs}" for obs in observations[:3])
    
    body = INITIAL_EMAIL_TEMPLATE.format(
        owner_name=owner_name.split()[0] if ' ' in owner_name else owner_name,
        company_context=company_context,
        personalized_observations=personalized_observations
    )
    
    # Generate subject
    if lead.city:
        subject = f"Quick thought about your {lead.city} website"
    elif lead.category:
        subject = f"A quick idea for your {lead.category.lower()} website"
    else:
        subject = "Quick thought about your website"
    
    return EmailDraft(subject=subject, body=body)


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
