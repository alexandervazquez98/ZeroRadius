from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.models import AdminUser
from app.services.dictionary_loader import dictionary_service
from app.services.audit import log_audit
from app.core.security import get_current_active_user

router = APIRouter(prefix="/dictionary", tags=["dictionary"])

class AttributeValue(BaseModel):
    name: str
    value: str | int

class AttributeInfo(BaseModel):
    name: str
    code: str | int
    type: str
    vendor: Optional[str] = None
    dictionary: Optional[str] = "Unknown"

@router.get("/files", response_model=List[str])
async def list_dictionary_files(current_user: AdminUser = Depends(get_current_active_user)):
    """List loaded dictionary files."""
    return dictionary_service.list_files()

@router.post("/upload")
async def upload_dictionary(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user)
):
    """Upload and validate a new dictionary file."""
    try:
        content = await file.read()
        dictionary_service.validate_and_save(file.filename, content)
        await log_audit(db, current_user.username, "UPLOAD", "dictionary", file.filename)
        return {"message": f"Dictionary {file.filename} uploaded and loaded successfully."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/attributes", response_model=List[AttributeInfo])
async def get_attributes(current_user: AdminUser = Depends(get_current_active_user)):
    """Get all available RADIUS attributes from loaded dictionary."""
    return dictionary_service.get_attributes()

@router.post("/rename")
async def rename_dictionary(
    old_name: str, 
    new_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user)
):
    """Rename a dictionary file."""
    try:
        dictionary_service.rename_file(old_name, new_name)
        await log_audit(db, current_user.username, "RENAME", "dictionary", old_name, new_value={"new_name": new_name})
        return {"message": f"File {old_name} renamed to {new_name}"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/values/{attribute_name}", response_model=List[AttributeValue])
async def get_attribute_values(
    attribute_name: str,
    current_user: AdminUser = Depends(get_current_active_user)
):
    """Get predefined values (enums) for a specific attribute."""
    return dictionary_service.get_values(attribute_name)
