# Implementation Plan: Enhancing Outreach Automation

## 1. Enhancing Website Scanning
- [ ] **Technical Audit**: Deepen checks for SEO tags, mobile responsiveness, and speed.
- [ ] **Content extraction**: Improve detection of projects, testimonials, licenses.
- [ ] **Decision Maker Identification**: Scan 'About Us' and 'Team' pages for names associated with "Owner", "CEO", "Founder".
- [ ] **Report Generation**: Generate a PDF/JSON audit report for the user.

## 2. Improving Email Verification
- [ ] **Integrate Verification Service**: Add Trumail or similar API for robust verification.
- [ ] **Smart Logic**: Handle blocked ports and catch-all domains gracefully.
- [ ] **Fallback Mechanisms**: If one method fails, try another.

## 3. Lead Enrichment
- [ ] **Data Merging**: Update the main Leads database with scanned info (Owner Name, Verified Email, Audit Score).
- [ ] **Owner Logic**: If multiple names found, pick the most likely decision maker.

## 4. Email Scheduling
- [ ] **Scheduler Module**: Implement a task queue (e.g., using `APScheduler` or `Celery`lite) to handle scheduled sends.
- [ ] **Timezone Handling**: Ensure emails are sent in the prospect's likely active hours.

## 5. Personalization
- [ ] **Template Engine**: Enhance the email template system to support dynamic variables like `{{owner_name}}`, `{{audit_summary}}`, `{{missing_elements}}`.
- [ ] **Content Injection**: Inject specific observations from the audit into the email body (e.g., "I noticed you don't have a portfolio listed...").
