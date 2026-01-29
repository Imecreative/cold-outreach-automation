
import asyncio
import time
import httpx
from openpyxl import Workbook
import os

async def test_upload():
    # Create a dummy large excel file
    filename = "large_test.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Name", "Email", "Website", "Category", "City"])
    for i in range(2000):
        ws.append([f"User {i}", f"user{i}@example.com", f"http://example.com/{i}", "Test", "Test City"])
    wb.save(filename)
    
    print(f"Created {filename} with 2000 rows.")
    
    start_time = time.time()
    async with httpx.AsyncClient() as client:
        with open(filename, "rb") as f:
            files = {"file": (filename, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            print("Uploading...")
            response = await client.post("http://127.0.0.1:8000/api/upload", files=files, timeout=30.0)
            
    end_time = time.time()
    
    if response.status_code == 200:
        print(f"Upload successful! Time taken: {end_time - start_time:.2f} seconds")
        print("Response:", response.json())
    else:
        print(f"Upload failed: {response.status_code}")
        print(response.text)
        
    os.remove(filename)

if __name__ == "__main__":
    asyncio.run(test_upload())
