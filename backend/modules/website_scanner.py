"""
Website Scanner Module.
Scans websites for technical SEO, content availability, and contact information.
"""

import asyncio
import time
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List, Set
import re
from urllib.parse import urljoin, urlparse

from ..models import WebsiteScanResult

class WebsiteScanner:
    """Scans websites for various metrics and content."""
    
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def scan(self, url: str) -> WebsiteScanResult:
        """
        Scans a single website and returns the results.
        """
        if not url:
             return WebsiteScanResult(
                url=url or "",
                summary="No URL provided"
            )
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        start_time = time.time()
        try:
            async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers)
                # We don't raise for status immediately to allow analyzing error pages if needed, 
                # but generally we want successful loads.
                if response.status_code >= 400:
                    return WebsiteScanResult(
                        url=url,
                        summary=f"Website returned status {response.status_code}"
                    )
                
                # Measure response time
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Parse content
                soup = BeautifulSoup(response.content, 'lxml')
                
                # Technical Audit
                tech_audit = self._audit_technical(soup, response)
                
                # Content Check
                content_audit = self._audit_content(soup)
                
                # Contact/Email finding
                emails = self._find_emails(response.text)
                
                # Generate summary
                summary = self._generate_summary(tech_audit, content_audit, emails)
                
                return WebsiteScanResult(
                    url=str(response.url),
                    title=tech_audit.get('title'),
                    meta_description=tech_audit.get('meta_description'),
                    response_time_ms=response_time_ms,
                    platform=tech_audit.get('platform'),
                    has_viewport_meta=tech_audit.get('has_viewport_meta', False),
                    audit_data={
                        'technical': tech_audit,
                        'content': content_audit,
                        'emails_found': list(emails)
                    },
                    summary=summary
                )

        except httpx.TimeoutException:
            return WebsiteScanResult(
                url=url,
                summary="Scan failed: Timeout (website too slow)"
            )
        except httpx.ConnectError:
             return WebsiteScanResult(
                url=url,
                summary="Scan failed: Connection refused or DNS error"
            )
        except Exception as e:
            return WebsiteScanResult(
                url=url,
                summary=f"Scan failed: {str(e)}"
            )

    def _audit_technical(self, soup: BeautifulSoup, response: httpx.Response) -> Dict[str, Any]:
        """Check technical aspects like TItle, Description, H1, Viewport."""
        audit = {}
        
        # Title
        title_tag = soup.find('title')
        audit['title'] = title_tag.get_text(strip=True) if title_tag else None
        
        # Meta Description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            meta_desc = soup.find('meta', attrs={'property': 'og:description'})
        audit['meta_description'] = meta_desc.get('content', '').strip() if meta_desc else None
        
        # H1
        h1 = soup.find('h1')
        audit['h1'] = h1.get_text(strip=True) if h1 else None
        
        # Viewport (Mobile responsiveness indicator)
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        audit['has_viewport_meta'] = bool(viewport)
        
        # Server/Platform detection (basic)
        headers = response.headers
        
        platform = "Unknown"
        text_lower = response.text.lower()
        
        if 'wordpress' in text_lower or 'wp-content' in text_lower:
             platform = "WordPress"
        elif 'wix' in text_lower:
            platform = "Wix"
        elif 'squarespace' in text_lower:
            platform = "Squarespace"
        elif 'shopify' in text_lower:
            platform = "Shopify"
        elif 'react' in text_lower or 'next.js' in text_lower:
            platform = "React/Next.js"
        elif 'laravel' in text_lower:
             platform = "Laravel"
            
        audit['platform'] = platform
        
        return audit

    def _audit_content(self, soup: BeautifulSoup) -> Dict[str, bool]:
        """Check for presence of specific content sections."""
        text_content = soup.get_text().lower()
        
        keywords = {
            'has_projects': ['project', 'portfolio', 'gallery', 'our work', 'case study', 'examples'],
            'has_testimonials': ['testimonial', 'review', 'what our clients say', 'feedback', 'stories'],
            'has_license': ['license', 'licence', 'insured', 'bonded', '#', 'registration'],
            'has_about': ['about us', 'our team', 'who we are', 'meet the team', 'story'],
            'has_services': ['services', 'what we do', 'offerings', 'solutions'],
            'has_social_links': ['facebook.com', 'instagram.com', 'linkedin.com', 'twitter.com', 'youtube.com']
        }
        
        audit = {}
        # First check all links as they are most reliable for specific sections
        links_href = set()
        for link in soup.find_all('a', href=True):
             links_href.add(link['href'].lower())
             
        for key, terms in keywords.items():
            found = False
            
            # Check links first
            for href in links_href:
                if any(term in href for term in terms):
                    found = True
                    break
            
            # If not in links, check visible text (less reliable but good fallback)
            if not found:
                 if any(term in text_content for term in terms):
                    found = True
            
            audit[key] = found
            
        return audit

    def _find_emails(self, text: str) -> Set[str]:
        """Find email addresses in text."""
        # Clean text slightly to avoid matching binary garbage if any
        # Basic regex for email extraction
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = set(re.findall(email_pattern, text))
        
        # Filter out common false positives or image extensions
        valid_emails = set()
        for email in emails:
            email_lower = email.lower()
            if not any(ext in email_lower for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css']):
                 valid_emails.add(email)
                 
        return valid_emails

    def _generate_summary(self, tech: Dict[str, Any], content: Dict[str, bool], emails: Set[str]) -> str:
        """Generate a human-readable summary of the scan."""
        issues = []
        goods = []
        
        # Technical
        if not tech.get('title'): issues.append("Missing Title tag")
        if not tech.get('meta_description'): issues.append("Missing Meta Description")
        if not tech.get('h1'): issues.append("Missing H1 tag")
        if not tech.get('has_viewport_meta'): issues.append("Not mobile responsive (no viewport)")
        
        # Content
        if not content.get('has_projects'): issues.append("No Projects/Portfolio found")
        if not content.get('has_testimonials'): issues.append("No Testimonials found")
        if not content.get('has_license'): issues.append("No License info found")
        
        # Goods
        if tech.get('has_viewport_meta'): goods.append("Mobile responsive")
        if content.get('has_projects'): goods.append("Has Portfolio")
        if content.get('has_testimonials'): goods.append("Has Testimonials")
        
        summary = ""
        
        # Priority: Platform
        if tech.get('platform') and tech.get('platform') != 'Unknown':
             summary += f"Built on {tech['platform']}. "
        
        if issues:
            summary += f"Missing: {', '.join(issues[:3])}"
            if len(issues) > 3:
                summary += f" (+{len(issues)-3} more)"
            summary += ". "
        else:
            summary += "Technically solid site. "
            
        if emails:
            email_list = list(emails)
            summary += f"Found contact: {email_list[0]}"
            if len(email_list) > 1:
                summary += f" (+{len(email_list)-1} others)"
            summary += "."
            
        return summary.strip()

# Standalone function for compatibility
async def scan_website(url: str) -> WebsiteScanResult:
    scanner = WebsiteScanner()
    return await scanner.scan(url)
