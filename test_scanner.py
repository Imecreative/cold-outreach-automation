import asyncio
from backend.modules.website_scanner import scan_website

async def main():
    urls = [
        "https://example.com",
        "https://www.google.com", 
        "https://github.com"
    ]
    
    print("Starting scan test...")
    for url in urls:
        print(f"\nScanning {url}...")
        result = await scan_website(url)
        print(f"Summary: {result.summary}")
        print(f"Title: {result.title}")
        print(f"Platform: {result.platform}")
        print(f"Viewport: {result.has_viewport_meta}")
        if result.audit_data:
             print(f"Emails: {result.audit_data.get('emails_found')}")
             print(f"Content: {result.audit_data.get('content')}")

if __name__ == "__main__":
    asyncio.run(main())
