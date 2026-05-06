# app/routes/upload.py

import os
import uuid
from fastapi import APIRouter, UploadFile, File

UPLOAD_DIR = "data/uploads"

router = APIRouter()

@router.post("/")
async def upload_files(files: list[UploadFile] = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_paths = []

    for file in files:
        file_id = str(uuid.uuid4())
        file_path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        file_paths.append(file_path)

    return {"files": file_paths}