"""
File management API routes for ResearchAgent.

Handles file uploads, listing, and analysis trigger.
"""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.api.models import FileUploadResponse
from backend.agents.research_agent import ResearchAgent
from backend.memory.conversation_memory import ConversationMemory
from backend.memory.storage import StorageManager
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("api.files")

router = APIRouter(prefix="/api", tags=["files"])

_storage: StorageManager = None
_agent: ResearchAgent = None


def init_file_routes(storage: StorageManager, agent: ResearchAgent):
    """Initialize file routes with dependencies.

    Args:
        storage: Storage manager instance.
        agent: Research agent instance.
    """
    global _storage, _agent
    _storage = storage
    _agent = agent


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload a file for analysis.

    Supported formats: PDF, TXT, CSV, Excel, JSON, Markdown.

    Args:
        file: Uploaded file.

    Returns:
        Upload confirmation with file details.
    """
    # Validate file size
    max_size = settings.max_upload_size_mb * 1024 * 1024
    file_size = 0

    # Generate unique filename
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix if file.filename else ".txt"
    safe_filename = f"{file_id}{ext}"
    upload_path = settings.uploads_path / safe_filename

    try:
        # Save file
        with open(upload_path, "wb") as buffer:
            while chunk := await file.read(8192):
                file_size += len(chunk)
                if file_size > max_size:
                    # Clean up oversized file
                    upload_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB"
                    )
                buffer.write(chunk)

        logger.info(f"File uploaded: {file.filename} -> {upload_path} ({file_size} bytes)")

        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename or "unknown",
            file_path=str(upload_path),
            size_bytes=file_size,
            content_type=file.content_type,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload error: {e}")
        # Clean up on error
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/files")
async def list_files():
    """List all uploaded files.

    Returns:
        List of uploaded file information.
    """
    uploads_dir = settings.uploads_path
    files = []

    for f in uploads_dir.iterdir():
        if f.is_file():
            stat = f.stat()
            files.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "created_at": stat.st_ctime,
                "path": str(f),
            })

    return {"files": sorted(files, key=lambda x: x["created_at"], reverse=True)}


@router.post("/files/{file_id}/analyze")
async def analyze_file(file_id: str, question: str = "Analyze this file and provide a summary"):
    """Analyze an uploaded file.

    Args:
        file_id: File ID (UUID from upload response).
        question: Question to answer about the file.

    Returns:
        Analysis results.
    """
    # Find the file
    uploads_dir = settings.uploads_path
    file_path = None

    for f in uploads_dir.iterdir():
        if f.name.startswith(file_id):
            file_path = f
            break

    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        memory = ConversationMemory(_storage)
        _agent.memory = memory
        result = await _agent.analyze_uploaded_file(str(file_path), question)
        return {"file_id": file_id, "analysis": result}
    except Exception as e:
        logger.error(f"File analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports")
async def list_reports():
    """List all generated reports.

    Returns:
        List of report files.
    """
    reports_dir = settings.reports_path
    reports = []

    for f in reports_dir.iterdir():
        if f.is_file() and f.suffix in ('.md', '.pdf'):
            stat = f.stat()
            reports.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "format": f.suffix.lstrip('.'),
                "created_at": stat.st_ctime,
                "path": str(f),
            })

    return {"reports": sorted(reports, key=lambda x: x["created_at"], reverse=True)}


@router.get("/reports/{filename}")
async def get_report(filename: str):
    """Get a generated report by filename.

    Args:
        filename: Report filename.

    Returns:
        Report content.
    """
    report_path = settings.reports_path / filename
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    content = report_path.read_text(encoding='utf-8')
    return {
        "filename": filename,
        "format": report_path.suffix.lstrip('.'),
        "content": content,
    }
