"""
File upload/download routes.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
from datetime import datetime

from ..config import DATA_DIR
from ..modules.excel_handler import load_excel, get_handler


router = APIRouter(prefix="/api", tags=["files"])


# Store current file path
_current_file_path: Path = None


def get_current_file_path() -> Path:
    return _current_file_path


def set_current_file_path(path: Path):
    global _current_file_path
    _current_file_path = path


@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    """
    Upload an Excel file with leads.
    """
    if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="Only Excel (.xlsx, .xls) and CSV (.csv) files are accepted")
    
    # Save uploaded file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"leads_{timestamp}.xlsx"
    file_path = DATA_DIR / safe_filename
    
    try:
        import aiofiles
        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # Read in 1MB chunks
                await buffer.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Load the Excel file (offload heavy processing to threadpool)
    try:
        from fastapi.concurrency import run_in_threadpool
        handler = await run_in_threadpool(load_excel, file_path)
        set_current_file_path(file_path)
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {str(e)}")
    
    return {
        "message": "File uploaded successfully",
        "filename": safe_filename,
        "leads_count": len(handler.leads),
        "columns": handler.all_columns
    }


@router.get("/download")
async def download_excel():
    """
    Download the current Excel file with all updates.
    """
    handler = get_handler()
    if not handler:
        raise HTTPException(status_code=404, detail="No Excel file loaded. Upload a file first.")
    
    # Save current state
    output_filename = f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_path = DATA_DIR / output_filename
    
    try:
        handler.save(output_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export Excel: {str(e)}")
    
    return FileResponse(
        path=output_path,
        filename=output_filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/status")
async def get_status():
    """
    Get current system status.
    """
    handler = get_handler()
    file_path = get_current_file_path()
    
    from ..modules.gmail_sender import get_daily_send_count, get_remaining_daily_quota
    from ..config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD
    
    # Quick check without actually connecting
    gmail_configured = bool(GMAIL_ADDRESS and GMAIL_APP_PASSWORD and 
                           GMAIL_ADDRESS != "your-email@gmail.com")
    
    return {
        "file_loaded": handler is not None,
        "current_file": str(file_path) if file_path else None,
        "leads_count": len(handler.leads) if handler else 0,
        "gmail_connected": gmail_configured,
        "gmail_message": "Configured" if gmail_configured else "Not configured - edit .env",
        "emails_sent_today": get_daily_send_count(),
        "emails_remaining_today": get_remaining_daily_quota()
    }
