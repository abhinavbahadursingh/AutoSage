from fastapi import APIRouter, UploadFile, File
router = APIRouter()

@router.post("/upload")
async def upload_dataset(project_id: str, file: UploadFile = File(...)):
    return {"filename": file.filename, "status": "uploaded"}

@router.get("/")
async def list_datasets(project_id: str):
    return []
