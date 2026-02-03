"""
Website Scanner Module.
Scans websites for technical SEO, content availability, contact information, and decision makers.
"""

import asyncio
import time
import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List, Set, Tuple
import re
from urllib.parse import urljoin, urlparse

from ..models import WebsiteScanResult
from .audit_report import AuditReportGenerator

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
                
                # Decision maker identification
                decision_makers = await self._find_decision_makers(url, client)
                
                # Generate summary
                summary = self._generate_summary(tech_audit, content_audit, emails, decision_makers)
                
                # Prepare full audit data
                audit_data = {
                    'technical': tech_audit,
                    'content': content_audit,
                    'emails_found': list(emails),
                    'decision_makers': decision_makers
                }
                
                # Generate audit report
                report_paths = None
                try:
                    report_gen = AuditReportGenerator()
                    report_paths = report_gen.generate_report(
                        url=str(response.url),
                        audit_data=audit_data,
                        decision_makers=decision_makers,
                        format="both"
                    )
                except Exception as e:
                    print(f"Failed to generate audit report: {e}")
                
                return WebsiteScanResult(
                    url=str(response.url),
                    title=tech_audit.get('title'),
                    meta_description=tech_audit.get('meta_description'),
                    response_time_ms=response_time_ms,
                    platform=tech_audit.get('platform'),
                    has_viewport_meta=tech_audit.get('has_viewport_meta', False),
                    audit_data=audit_data,
                    summary=summary,
                    audit_report_paths=report_paths
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
        
        # SSL Check
        audit['ssl_enabled'] = str(response.url).startswith('https://')
        
        # Structured Data Check (Schema.org)
        structured_data = soup.find('script', type='application/ld+json')
        audit['has_structured_data'] = bool(structured_data)
        
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
    
    async def _find_decision_makers(self, base_url: str, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """
        Find decision makers by scanning About Us and Team pages.
        Returns list of decision makers with names, titles, and confidence scores.
        """
        decision_makers = []
        
        # Common About/Team page patterns
        about_patterns = [
            '/about', '/about-us', '/team', '/our-team', '/meet-the-team',
            '/leadership', '/staff', '/who-we-are', '/contact'
        ]
        
        # Parse base URL
        parsed = urlparse(base_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Try to find and scan about/team pages
        for pattern in about_patterns:
            try:
                about_url = base_domain + pattern
                response = await client.get(about_url, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'lxml')
                    found_makers = self._extract_decision_makers_from_page(soup)
                    decision_makers.extend(found_makers)
                    
                    # Break after first successful page to avoid duplicates
                    if found_makers:
                        break
            except:
                continue
        
        # Remove duplicates and rank by confidence
        unique_makers = self._deduplicate_decision_makers(decision_makers)
        return sorted(unique_makers, key=lambda x: x['confidence'], reverse=True)[:5]
    
    def _extract_decision_makers_from_page(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract decision maker names and titles from a page.
        Uses pattern matching to identify Owner, CEO, Founder, etc.
        """
        decision_makers = []
        text = soup.get_text()
        
        # Title keywords with confidence weights
        title_keywords = {
            'owner': 90,
            'ceo': 85,
            'chief executive': 85,
            'founder': 80,
            'president': 75,
            'principal': 70,
            'managing director': 70,
            'director': 60,
            'manager': 50
        }
        
        # Pattern to find "Name - Title" or "Title: Name" combinations
        # This regex looks for capitalized names near title keywords
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            for title_keyword, base_confidence in title_keywords.items():
                if title_keyword in line_lower:
                    # Try to extract name from this line or nearby lines
                    name = self._extract_name_from_text(line)
                    
                    if name:
                        decision_makers.append({
                            'name': name,
                            'title': title_keyword.title(),
                            'confidence': base_confidence,
                            'source': 'about_page'
                        })
                    else:
                        # Check adjacent lines for name
                        for offset in [-1, 1]:
                            adj_index = i + offset
                            if 0 <= adj_index < len(lines):
                                name = self._extract_name_from_text(lines[adj_index])
                                if name:
                                    decision_makers.append({
                                        'name': name,
                                        'title': title_keyword.title(),
                                        'confidence': base_confidence - 10,
                                        'source': 'about_page'
                                    })
                                    break
        
        return decision_makers
    
    def _extract_name_from_text(self, text: str) -> Optional[str]:
        """
        Extract a person's name from text using pattern matching.
        Looks for capitalized words that match name patterns.
        """
        # Clean the text
        text = text.strip()
        
        # Remove common prefixes/context words
        text = re.sub(r'(by|with|meet|contact|email|call|reach)\s+', '', text, flags=re.IGNORECASE)
        
        # Pattern for detecting names: 2-3 capitalized words
        # Matches: "John Smith", "Mary Jane Doe"
        name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b'
        
        matches = re.findall(name_pattern, text)
        
        if matches:
            # Return the first match that looks like a name
            for match in matches:
                # Filter out common false positives
                if match.lower() not in ['home', 'about us', 'contact us', 'our team', 'learn more']:
                    words = match.split()
                    # Valid name should have 2-3 words
                    if 2 <= len(words) <= 3:
                        return match
        
        return None
    
    def _deduplicate_decision_makers(self, makers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate decision makers, keeping highest confidence.
        """
        seen_names = {}
        
        for maker in makers:
            name = maker['name'].lower()
            if name not in seen_names or maker['confidence'] > seen_names[name]['confidence']:
                seen_names[name] = maker
        
        return list(seen_names.values())

    def _generate_summary(self, tech: Dict[str, Any], content: Dict[str, bool], emails: Set[str], decision_makers: List[Dict[str, Any]] = None) -> str:
        """Generate a human-readable summary of the scan."""
        issues = []
        goods = []
        
        # Technical
        if not tech.get('title'): issues.append("Missing Title tag")
        if not tech.get('meta_description'): issues.append("Missing Meta Description")
        if not tech.get('h1'): issues.append("Missing H1 tag")
        if not tech.get('has_viewport_meta'): issues.append("Not mobile responsive (no viewport)")
        if not tech.get('ssl_enabled'): issues.append("No SSL certificate")
        
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
        
        # Decision makers
        if decision_makers and len(decision_makers) > 0:
            primary = decision_makers[0]
            summary += f"Found: {primary['name']} ({primary['title']}). "
        
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
