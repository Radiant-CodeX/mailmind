from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables from `.env` early so settings and GraphClient
# pick up Azure credentials when the application imports configuration.
load_dotenv()

from app.api.routes import router
from app.queue.queue import EmailQueue


# Create the FastAPI application and mount the API router.
# The shared email queue is stored on the application state so
# it can be accessed from route handlers during request processing.
app = FastAPI(title="MailMind Backend")
app.include_router(router)
app.state.email_queue = EmailQueue()
