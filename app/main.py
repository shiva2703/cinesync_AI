from fastapi import FastAPI
from app.routes import upload, generate, health

app = FastAPI(title="CineSync AI")

app.include_router(upload.router, prefix="/upload", tags=["Upload"])
app.include_router(generate.router, prefix="/generate", tags=["Generate"])
app.include_router(health.router, prefix="/health", tags=["Health"])


@app.get("/")
def root():
    return {"message": "CineSync AI Backend Running"}