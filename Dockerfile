FROM python:3.11-slim

WORKDIR /app

# Since you set the Railway Root Directory to `backend`, the context is `backend`.
# Therefore, requirements.txt is in the root of the build context.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application
COPY . .

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
