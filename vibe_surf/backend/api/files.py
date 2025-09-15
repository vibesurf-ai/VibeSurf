"""
File Upload and Management Router

Handles file uploads to workspace directories, file retrieval, and listing
of uploaded files for VibeSurf sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
import os
import shutil
import logging
from datetime import datetime
from uuid_extensions import uuid7str
import mimetypes
from pathlib import Path

from ..database import get_db_session
from ..database.queries import UploadedFileQueries
from .models import FileListQueryRequest, SessionFilesQueryRequest

from vibe_surf.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


def get_upload_directory(session_id: Optional[str] = None) -> str:
    from ..shared_state import workspace_dir
    """Get the upload directory path for a session or global uploads"""
    if session_id:
        upload_dir = os.path.join(workspace_dir, "sessions", session_id, "upload_files")
    else:
        upload_dir = os.path.join(workspace_dir, "sessions", "upload_files")

    # Create directory if it doesn't exist
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def is_safe_path(basedir: str, path: str) -> bool:
    """Check if the path is safe (within basedir)"""
    try:
        # Resolve both paths to absolute paths
        basedir = os.path.abspath(basedir)
        path = os.path.abspath(path)

        # Check if path starts with basedir
        return path.startswith(basedir)
    except:
        return False


@router.post("/upload")
async def upload_files(
        files: List[UploadFile] = File(...),
        session_id: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db_session)
):
    """Upload files to workspace/upload_files folder or session-specific folder"""
    try:
        from ..shared_state import workspace_dir

        upload_dir = get_upload_directory(session_id)
        uploaded_file_info = []

        for file in files:
            if not file.filename:
                continue

            # Generate unique file ID
            file_id = uuid7str()

            # Create safe filename
            filename = file.filename
            file_path = os.path.join(upload_dir, filename)

            # Handle duplicate filenames by adding suffix
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(file_path):
                new_filename = f"{base_name}_{counter}{ext}"
                file_path = os.path.join(upload_dir, new_filename)
                filename = new_filename
                counter += 1

            # Ensure path is safe
            if not is_safe_path(upload_dir, file_path):
                raise HTTPException(status_code=400, detail=f"Invalid file path: {filename}")

            # Save file
            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                # Get file info
                file_size = os.path.getsize(file_path)
                mime_type, _ = mimetypes.guess_type(file_path)
                relative_path = os.path.relpath(file_path, workspace_dir)

                # Store file metadata in database
                uploaded_file = await UploadedFileQueries.create_file_record(
                    db=db,
                    file_id=file_id,
                    original_filename=file.filename,
                    stored_filename=filename,
                    file_path=file_path,
                    session_id=session_id,
                    file_size=file_size,
                    mime_type=mime_type or "application/octet-stream",
                    relative_path=relative_path
                )

                # Create response metadata
                file_metadata = {
                    "file_id": uploaded_file.file_id,
                    "original_filename": uploaded_file.original_filename,
                    "stored_filename": uploaded_file.stored_filename,
                    "session_id": uploaded_file.session_id,
                    "file_size": uploaded_file.file_size,
                    "mime_type": uploaded_file.mime_type,
                    "upload_time": uploaded_file.upload_time.isoformat(),
                    "file_path": file_path
                }

                uploaded_file_info.append(file_metadata)

                logger.info(f"File uploaded: {filename} (ID: {file_id}) to {upload_dir}")

            except Exception as e:
                logger.error(f"Failed to save file {filename}: {e}")
                # If database record was created but file save failed, clean up
                try:
                    await UploadedFileQueries.hard_delete_file(db, file_id)
                except:
                    pass
                raise HTTPException(status_code=500, detail=f"Failed to save file {filename}: {str(e)}")

        # Commit all database changes
        await db.commit()

        return {
            "message": f"Successfully uploaded {len(uploaded_file_info)} files",
            "files": uploaded_file_info,
            "upload_directory": upload_dir
        }

    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


@router.get("/{file_id}")
async def download_file(file_id: str, db: AsyncSession = Depends(get_db_session)):
    """Download file by file ID"""
    from ..shared_state import workspace_dir

    uploaded_file = await UploadedFileQueries.get_file(db, file_id)
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = uploaded_file.file_path

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Ensure path is safe
    if not is_safe_path(workspace_dir, file_path):
        raise HTTPException(status_code=403, detail="Access denied")

    return FileResponse(
        path=file_path,
        filename=uploaded_file.original_filename,
        media_type=uploaded_file.mime_type
    )


@router.get("")
async def list_uploaded_files(
        query: FileListQueryRequest = Depends(),
        db: AsyncSession = Depends(get_db_session)
):
    """List uploaded files, optionally filtered by session"""
    try:
        # Get files from database
        uploaded_files = await UploadedFileQueries.list_files(
            db=db,
            session_id=query.session_id,
            limit=query.limit,
            offset=query.offset,
            active_only=True
        )

        # Get total count
        total_count = await UploadedFileQueries.count_files(
            db=db,
            session_id=query.session_id,
            active_only=True
        )

        # Convert to response format (exclude file_path for security)
        files_response = []
        for file_record in uploaded_files:
            files_response.append({
                "file_id": file_record.file_id,
                "original_filename": file_record.original_filename,
                "stored_filename": file_record.stored_filename,
                "session_id": file_record.session_id,
                "file_size": file_record.file_size,
                "mime_type": file_record.mime_type,
                "upload_time": file_record.upload_time.isoformat(),
                "file_path": file_record.file_path
            })

        return {
            "files": files_response,
            "total_count": total_count,
            "limit": query.limit,
            "offset": query.offset,
            "has_more": query.limit != -1 and (query.offset + query.limit < total_count),
            "session_id": query.session_id
        }

    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.delete("/{file_id}")
async def delete_file(file_id: str, db: AsyncSession = Depends(get_db_session)):
    """Delete uploaded file by file ID"""
    # Get file record
    uploaded_file = await UploadedFileQueries.get_file(db, file_id)
    if not uploaded_file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Remove file from disk
        if os.path.exists(uploaded_file.file_path):
            os.remove(uploaded_file.file_path)

        # Soft delete from database
        success = await UploadedFileQueries.delete_file(db, file_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete file record")

        await db.commit()

        return {
            "message": f"File {uploaded_file.original_filename} deleted successfully",
            "file_id": file_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file {file_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.get("/session/{session_id}")
async def list_session_files(
        session_id: str,
        query: SessionFilesQueryRequest = Depends()
):
    """List all files in a session directory"""
    try:
        from ..shared_state import workspace_dir
        session_dir = os.path.join(workspace_dir, session_id)

        if not os.path.exists(session_dir):
            return {
                "session_id": session_id,
                "files": [],
                "directories": [],
                "message": "Session directory not found"
            }

        files = []
        directories = []

        for root, dirs, filenames in os.walk(session_dir):
            # Calculate relative path from session directory
            rel_root = os.path.relpath(root, session_dir)
            if rel_root == ".":
                rel_root = ""

            # Add directories if requested
            if query.include_directories:
                for dirname in dirs:
                    dir_path = os.path.join(rel_root, dirname) if rel_root else dirname
                    directories.append({
                        "name": dirname,
                        "path": dir_path,
                        "type": "directory"
                    })

            # Add files
            for filename in filenames:
                file_path = os.path.join(root, filename)
                rel_path = os.path.join(rel_root, filename) if rel_root else filename

                try:
                    stat = os.stat(file_path)
                    mime_type, _ = mimetypes.guess_type(file_path)

                    files.append({
                        "name": filename,
                        "path": rel_path,
                        "size": stat.st_size,
                        "mime_type": mime_type or "application/octet-stream",
                        "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "type": "file"
                    })
                except Exception as e:
                    logger.warning(f"Could not get stats for file {file_path}: {e}")

        return {
            "session_id": session_id,
            "files": files,
            "directories": directories if query.include_directories else [],
            "total_files": len(files),
            "total_directories": len(directories) if query.include_directories else 0
        }

    except Exception as e:
        logger.error(f"Failed to list session files for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list session files: {str(e)}")
