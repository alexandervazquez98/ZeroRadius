from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import AdminUser
from app.services.dictionary_loader import dictionary_service
from app.services.audit import log_audit
from app.core.security import get_current_active_user
import logging
import docker as docker_sdk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dictionary", tags=["dictionary"])


def _reload_radius() -> None:
    """Restart the radius-server container so it re-reads custom dictionaries.

    FreeRADIUS only loads dictionaries at startup.  After uploading,
    editing or deleting a dictionary file the container must be restarted
    for the changes to take effect.
    """
    try:
        client = docker_sdk.from_env()
        container = client.containers.get("radius-server")
        container.restart(timeout=5)
        logger.info("radius-server restarted to reload custom dictionaries")
    except Exception as exc:
        logger.warning("Could not restart radius-server: %s", exc)


# ---------- Schemas ----------


class AttributeValue(BaseModel):
    name: str
    value: str | int


class AttributeInfo(BaseModel):
    name: str
    code: str | int
    type: str
    vendor: Optional[str] = None
    dictionary: Optional[str] = "Unknown"


class ContentBody(BaseModel):
    content: str


# ---------- File CRUD ----------


@router.get("/files", response_model=List[str])
async def list_dictionary_files(
    current_user: AdminUser = Depends(get_current_active_user),
):
    """List loaded dictionary files."""
    return dictionary_service.list_files()


@router.post("/upload")
async def upload_dictionary(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Upload and validate a new dictionary file (auto-converts v4 types)."""
    try:
        content = await file.read()
        result = dictionary_service.validate_and_save(
            file.filename or "unknown",
            content,
        )
        msg = f"Dictionary {file.filename} uploaded successfully."
        if result["conversions"] > 0:
            msg += (
                f" {result['conversions']} FreeRADIUS 4.x type(s) were "
                "auto-converted to 3.x equivalents."
            )
        if result.get("renames"):
            msg += (
                f" {len(result['renames'])} vendor attribute(s) were "
                f"auto-renamed to avoid collisions: "
                f"{', '.join(result['renames'])}."
            )
        await log_audit(
            db,
            current_user.username,
            "UPLOAD",
            "dictionary",
            file.filename,
        )
        _reload_radius()
        return {"message": msg}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rename")
async def rename_dictionary(
    old_name: str,
    new_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Rename a dictionary file."""
    try:
        dictionary_service.rename_file(old_name, new_name)
        await log_audit(
            db,
            current_user.username,
            "RENAME",
            "dictionary",
            old_name,
            new_value={"new_name": new_name},
        )
        _reload_radius()
        return {"message": f"File {old_name} renamed to {new_name}"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{filename}")
async def delete_dictionary(
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Delete a dictionary file."""
    try:
        dictionary_service.delete_file(filename)
        await log_audit(
            db,
            current_user.username,
            "DELETE",
            "dictionary",
            filename,
        )
        _reload_radius()
        return {"message": f"Dictionary {filename} deleted."}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Content (read / edit) ----------


@router.get("/content/{filename}")
async def get_dictionary_content(
    filename: str,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Return the raw text content of a dictionary file."""
    try:
        content = dictionary_service.read_content(filename)
        return {"filename": filename, "content": content}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/content/{filename}")
async def update_dictionary_content(
    filename: str,
    body: ContentBody,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Overwrite a dictionary file with new content (auto-converts v4 types)."""
    try:
        result = dictionary_service.write_content(filename, body.content)
        msg = f"Dictionary {filename} updated successfully."
        if result["conversions"] > 0:
            msg += (
                f" {result['conversions']} FreeRADIUS 4.x type(s) were "
                "auto-converted to 3.x equivalents."
            )
        if result.get("renames"):
            msg += (
                f" {len(result['renames'])} vendor attribute(s) were "
                f"auto-renamed to avoid collisions: "
                f"{', '.join(result['renames'])}."
            )
        await log_audit(
            db,
            current_user.username,
            "UPDATE",
            "dictionary",
            filename,
        )
        _reload_radius()
        return {"message": msg}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Attribute queries ----------


@router.get("/attributes", response_model=List[AttributeInfo])
async def get_attributes(
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Get all available RADIUS attributes from loaded dictionaries."""
    return dictionary_service.get_attributes()


@router.get("/values/{attribute_name}", response_model=List[AttributeValue])
async def get_attribute_values(
    attribute_name: str,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Get predefined values (enums) for a specific attribute."""
    return dictionary_service.get_values(attribute_name)


# ---------- FreeRADIUS logs ----------


@router.get("/radius-logs")
async def get_radius_logs(
    lines: int = 80,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Return recent FreeRADIUS container logs for dictionary diagnostics.

    Filters the output to show only dictionary-related lines (includes,
    errors, warnings) plus the last startup status.
    """
    try:
        client = docker_sdk.from_env()
        container = client.containers.get("radius-server")
        raw_logs = container.logs(tail=lines, timestamps=False).decode(
            "utf-8", errors="replace"
        )

        all_lines = raw_logs.splitlines()

        # Filter for dictionary/startup relevant lines
        keywords = [
            "dictionary",
            "dict_init",
            "dict_add",
            "Duplicate attribute",
            "Error",
            "error",
            "Warning",
            "warning",
            "Including custom",
            "Skipping duplicate",
            "Starting -",
            "Ready to process",
            "Listening on",
            "Exiting",
            "removed v4 keyword",
        ]
        filtered = [
            ln for ln in all_lines if any(kw.lower() in ln.lower() for kw in keywords)
        ]

        # Determine overall status
        status = "unknown"
        for ln in reversed(all_lines):
            if "Ready to process requests" in ln:
                status = "running"
                break
            if "Exiting normally" in ln or "Error" in ln.lower():
                status = "error"
                break

        return {
            "status": status,
            "total_lines": len(all_lines),
            "filtered_lines": len(filtered),
            "logs": filtered[-50:],  # last 50 relevant lines
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "total_lines": 0,
            "filtered_lines": 0,
            "logs": [f"Could not fetch logs: {exc}"],
        }
