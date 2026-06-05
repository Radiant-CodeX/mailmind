import os

from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

TENANT_ID = os.getenv("TENANT_ID", "common")
CLIENT_ID = os.getenv("CLIENT_ID")
GRAPH_SCOPE = ["User.Read", "Mail.Read"]

FRONTEND_ORIGIN = "http://localhost:3000"