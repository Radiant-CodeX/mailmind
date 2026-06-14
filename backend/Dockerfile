FROM python:3.11-slim

WORKDIR /app

# The context is already the backend folder, so we copy requirements directly
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the spaCy model used for date NER (commitment extraction) and PII
# detection. Without this the app boots but logs "en_core_web_sm not loaded"
# and silently degrades to regex-only extraction.
RUN python -m spacy download en_core_web_sm

# Copy the rest of the backend files
COPY . .

# Start the server using the robust port binding format
# CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]