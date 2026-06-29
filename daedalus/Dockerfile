FROM python:3.13-slim

# Workdir inside the container
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN adduser --disabled-password --gecos "" myuser && \
    chown -R myuser:myuser /app

# Copy the rest of the code
COPY . .

USER myuser

# Make sure local bin is on PATH
ENV PATH="/home/myuser/.local/bin:$PATH"

# Default port (Cloud Run/GKE use PORT env var)
ENV PORT=8080

# Start FastAPI/ADK via uvicorn
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
