from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import emails, tasks, triage

app = FastAPI(title="MailMind API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development, allow all origins.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(emails.router, prefix="/api", tags=["emails"])
app.include_router(triage.router, prefix="/api", tags=["triage"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])

@app.get("/")
async def root():
    return {"status": "running"}