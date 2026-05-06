# app/models/request_models.py

from pydantic import BaseModel
from typing import List

class GenerateRequest(BaseModel):
    files: List[str]
    prompt: str