"""
Audit Report Generator Module.
Generates detailed website audit reports in JSON and PDF formats.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class AuditReportGenerator:
    """Generates comprehensive audit reports from website scan data."""
    
    def __init__(self, output_dir: str = "data/audit_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(
        self, 
        url: str, 
        audit_data: Dict[str, Any],
        decision_makers: List[Dict[str, Any]] = None,
        format: str = "both"  # "json", "pdf", or "both"
    ) -> Dict[str, str]:
        """
        Generate audit report in specified format(s).
        
        Returns:
            Dict with paths to generated files: {"json": path, "pdf": path}
        """
        # Create report data structure
        report_data = self._create_report_data(url, audit_data, decision_makers)
        
        # Generate unique filename based on domain and timestamp
        domain = url.split("//")[-1].split("/")[0].replace("www.", "")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{domain}_{timestamp}"
        
        result = {}
        
        # Generate JSON
        if format in ["json", "both"]:
            json_path = self.output_dir / f"{base_filename}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            result["json"] = str(json_path)
        
        # Generate PDF
        if format in ["pdf", "both"]:
            pdf_path = self.output_dir / f"{base_filename}.pdf"
            self._generate_pdf(report_data, str(pdf_path))
            result["pdf"] = str(pdf_path)
        
        return result
    
    def _create_report_data(
        self, 
        url: str, 
        audit_data: Dict[str, Any],
        decision_makers: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create structured report data."""
        tech = audit_data.get('technical', {})
        content = audit_data.get('content', {})
        
        # Calculate scores
        seo_score = self._calculate_seo_score(tech)
        content_score = self._calculate_content_score(content)
        overall_score = int((seo_score + content_score) / 2)
        
        return {
            "report_metadata": {
                "url": url,
                "generated_at": datetime.now().isoformat(),
                "report_version": "1.0"
            },
            "executive_summary": {
                "overall_score": overall_score,
                "seo_score": seo_score,
                "content_score": content_score,
                "grade": self._score_to_grade(overall_score),
                "key_findings": self._generate_key_findings(tech, content)
            },
            "technical_seo": {
                "score": seo_score,
                "details": {
                    "title": tech.get('title'),
                    "has_title": bool(tech.get('title')),
                    "meta_description": tech.get('meta_description'),
                    "has_meta_description": bool(tech.get('meta_description')),
                    "h1_tag": tech.get('h1'),
                    "has_h1": bool(tech.get('h1')),
                    "mobile_responsive": tech.get('has_viewport_meta', False),
                    "platform": tech.get('platform', 'Unknown'),
                    "ssl_enabled": tech.get('ssl_enabled', None),
                    "has_structured_data": tech.get('has_structured_data', False)
                },
                "issues": self._get_technical_issues(tech),
                "recommendations": self._get_technical_recommendations(tech)
            },
            "content_analysis": {
                "score": content_score,
                "details": {
                    "has_projects": content.get('has_projects', False),
                    "has_testimonials": content.get('has_testimonials', False),
                    "has_license": content.get('has_license', False),
                    "has_about": content.get('has_about', False),
                    "has_services": content.get('has_services', False),
                    "has_social_links": content.get('has_social_links', False)
                },
                "found_elements": self._get_found_elements(content),
                "missing_elements": self._get_missing_elements(content),
                "recommendations": self._get_content_recommendations(content)
            },
            "decision_makers": decision_makers or [],
            "emails_found": audit_data.get('emails_found', []),
            "action_items": self._generate_action_items(tech, content)
        }
    
    def _calculate_seo_score(self, tech: Dict[str, Any]) -> int:
        """Calculate SEO score (0-100)."""
        score = 0
        
        # Title tag (20 points)
        if tech.get('title'):
            score += 20
        
        # Meta description (20 points)
        if tech.get('meta_description'):
            score += 20
        
        # H1 tag (15 points)
        if tech.get('h1'):
            score += 15
        
        # Mobile responsive (25 points)
        if tech.get('has_viewport_meta'):
            score += 25
        
        # SSL (10 points)
        if tech.get('ssl_enabled'):
            score += 10
        
        # Structured data (10 points)
        if tech.get('has_structured_data'):
            score += 10
        
        return score
    
    def _calculate_content_score(self, content: Dict[str, Any]) -> int:
        """Calculate content score (0-100)."""
        score = 0
        max_per_item = 100 // 6  # 6 key content elements
        
        if content.get('has_projects'):
            score += max_per_item
        if content.get('has_testimonials'):
            score += max_per_item
        if content.get('has_license'):
            score += max_per_item
        if content.get('has_about'):
            score += max_per_item
        if content.get('has_services'):
            score += max_per_item
        if content.get('has_social_links'):
            score += max_per_item
        
        return min(score, 100)
    
    def _score_to_grade(self, score: int) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def _get_technical_issues(self, tech: Dict[str, Any]) -> List[str]:
        """Extract technical issues."""
        issues = []
        if not tech.get('title'):
            issues.append("Missing title tag")
        if not tech.get('meta_description'):
            issues.append("Missing meta description")
        if not tech.get('h1'):
            issues.append("Missing H1 tag")
        if not tech.get('has_viewport_meta'):
            issues.append("Not mobile responsive")
        if tech.get('ssl_enabled') is False:
            issues.append("SSL certificate not detected")
        return issues
    
    def _get_technical_recommendations(self, tech: Dict[str, Any]) -> List[str]:
        """Generate technical recommendations."""
        recs = []
        if not tech.get('title'):
            recs.append("Add a descriptive title tag (50-60 characters)")
        if not tech.get('meta_description'):
            recs.append("Add meta description to improve click-through rate")
        if not tech.get('has_viewport_meta'):
            recs.append("Make website mobile-responsive - 60% of traffic is mobile")
        if not tech.get('has_structured_data'):
            recs.append("Add Schema.org structured data for better search visibility")
        return recs
    
    def _get_found_elements(self, content: Dict[str, Any]) -> List[str]:
        """Get list of found content elements."""
        found = []
        mapping = {
            'has_projects': 'Projects/Portfolio',
            'has_testimonials': 'Customer Testimonials',
            'has_license': 'License Information',
            'has_about': 'About Us Section',
            'has_services': 'Services List',
            'has_social_links': 'Social Media Links'
        }
        for key, label in mapping.items():
            if content.get(key):
                found.append(label)
        return found
    
    def _get_missing_elements(self, content: Dict[str, Any]) -> List[str]:
        """Get list of missing content elements."""
        missing = []
        mapping = {
            'has_projects': 'Projects/Portfolio',
            'has_testimonials': 'Customer Testimonials',
            'has_license': 'License Information',
            'has_about': 'About Us Section',
            'has_services': 'Services List',
            'has_social_links': 'Social Media Links'
        }
        for key, label in mapping.items():
            if not content.get(key):
                missing.append(label)
        return missing
    
    def _get_content_recommendations(self, content: Dict[str, Any]) -> List[str]:
        """Generate content recommendations."""
        recs = []
        if not content.get('has_projects'):
            recs.append("Add a portfolio showcasing completed projects")
        if not content.get('has_testimonials'):
            recs.append("Display customer testimonials to build trust")
        if not content.get('has_license'):
            recs.append("Display license numbers prominently")
        if not content.get('has_about'):
            recs.append("Add an About Us page introducing your team")
        return recs
    
    def _generate_key_findings(self, tech: Dict[str, Any], content: Dict[str, Any]) -> List[str]:
        """Generate top 3-5 key findings."""
        findings = []
        
        # Technical findings
        if not tech.get('has_viewport_meta'):
            findings.append("Website is not mobile-friendly")
        if not tech.get('title') or not tech.get('meta_description'):
            findings.append("Missing critical SEO elements")
        
        # Content findings
        if not content.get('has_projects'):
            findings.append("No portfolio to showcase work")
        if not content.get('has_testimonials'):
            findings.append("Missing social proof (testimonials)")
        if not content.get('has_license'):
            findings.append("License information not displayed")
        
        # Platform
        if tech.get('platform') != 'Unknown':
            findings.append(f"Running on {tech['platform']}")
        
        return findings[:5]
    
    def _generate_action_items(self, tech: Dict[str, Any], content: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate prioritized action items."""
        actions = []
        
        # High priority
        if not tech.get('has_viewport_meta'):
            actions.append({
                "priority": "High",
                "action": "Make website mobile-responsive",
                "impact": "60% of visitors use mobile devices"
            })
        
        if not content.get('has_license'):
            actions.append({
                "priority": "High",
                "action": "Display license and insurance information",
                "impact": "Builds trust with potential customers"
            })
        
        # Medium priority
        if not tech.get('meta_description'):
            actions.append({
                "priority": "Medium",
                "action": "Add meta descriptions to pages",
                "impact": "Improves search engine click-through rate"
            })
        
        if not content.get('has_projects'):
            actions.append({
                "priority": "Medium",
                "action": "Create portfolio/project gallery",
                "impact": "Visual proof of quality work"
            })
        
        # Low priority
        if not content.get('has_social_links'):
            actions.append({
                "priority": "Low",
                "action": "Add social media links",
                "impact": "Increases engagement and credibility"
            })
        
        return actions
    
    def _generate_pdf(self, report_data: Dict[str, Any], output_path: str):
        """Generate PDF report using ReportLab."""
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c5aa0'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Title
        story.append(Paragraph("Website Audit Report", title_style))
        story.append(Spacer(1, 0.2 * inch))
        
        # Metadata
        metadata = report_data['report_metadata']
        story.append(Paragraph(f"<b>Website:</b> {metadata['url']}", styles['Normal']))
        story.append(Paragraph(f"<b>Generated:</b> {metadata['generated_at'][:10]}", styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))
        
        # Executive Summary
        summary = report_data['executive_summary']
        story.append(Paragraph("Executive Summary", heading_style))
        
        # Score table
        score_data = [
            ['Metric', 'Score', 'Grade'],
            ['Overall Score', f"{summary['overall_score']}/100", summary['grade']],
            ['SEO Score', f"{summary['seo_score']}/100", self._score_to_grade(summary['seo_score'])],
            ['Content Score', f"{summary['content_score']}/100", self._score_to_grade(summary['content_score'])]
        ]
        
        score_table = Table(score_data, colWidths=[2*inch, 1.5*inch, 1*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(score_table)
        story.append(Spacer(1, 0.2 * inch))
        
        # Key Findings
        if summary['key_findings']:
            story.append(Paragraph("<b>Key Findings:</b>", styles['Normal']))
            for finding in summary['key_findings']:
                story.append(Paragraph(f"• {finding}", styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))
        
        # Technical SEO
        tech_seo = report_data['technical_seo']
        story.append(Paragraph("Technical SEO Analysis", heading_style))
        
        if tech_seo['issues']:
            story.append(Paragraph("<b>Issues Found:</b>", styles['Normal']))
            for issue in tech_seo['issues']:
                story.append(Paragraph(f"• {issue}", styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
        
        if tech_seo['recommendations']:
            story.append(Paragraph("<b>Recommendations:</b>", styles['Normal']))
            for rec in tech_seo['recommendations']:
                story.append(Paragraph(f"• {rec}", styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))
        
        # Content Analysis
        content = report_data['content_analysis']
        story.append(Paragraph("Content Analysis", heading_style))
        
        if content['found_elements']:
            story.append(Paragraph(f"<b>Found ({len(content['found_elements'])}):</b> " + 
                                 ", ".join(content['found_elements']), styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
        
        if content['missing_elements']:
            story.append(Paragraph(f"<b>Missing ({len(content['missing_elements'])}):</b> " + 
                                 ", ".join(content['missing_elements']), styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))
        
        # Decision Makers
        if report_data['decision_makers']:
            story.append(Paragraph("Decision Makers Found", heading_style))
            for dm in report_data['decision_makers']:
                story.append(Paragraph(f"• {dm['name']} - {dm.get('title', 'N/A')}", styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))
        
        # Action Items
        if report_data['action_items']:
            story.append(Paragraph("Recommended Actions", heading_style))
            
            action_data = [['Priority', 'Action', 'Impact']]
            for action in report_data['action_items']:
                action_data.append([
                    action['priority'],
                    action['action'],
                    action['impact']
                ])
            
            action_table = Table(action_data, colWidths=[1*inch, 2.5*inch, 2.5*inch])
            action_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))
            
            story.append(action_table)
        
        # Build PDF
        doc.build(story)
