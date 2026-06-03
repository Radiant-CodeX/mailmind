from fastapi import FastAPI

app = FastAPI(title="MailMind API")

@app.get("/")
async def root():
    return {"status": "running"}