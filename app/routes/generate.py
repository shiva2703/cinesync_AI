# app/routes/generate.py

from fastapi import APIRouter
from app.models.request_models import GenerateRequest
from app.pipeline.pipeline import run_pipeline

router = APIRouter()

@router.post("/")
def generate_video(request: GenerateRequest):
    output_path = run_pipeline(
        files=request.files,
        prompt=request.prompt
    )

    return {"output": output_path}