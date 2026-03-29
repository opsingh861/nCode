FROM python:3.11-slim
WORKDIR /app

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ backend/

# Create temp directory
RUN mkdir -p /app/tmp

ENV TEMP_DIR=/app/tmp
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
