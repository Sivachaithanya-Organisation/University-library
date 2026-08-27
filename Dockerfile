# University Library — Flask application container
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY templates/ templates/
COPY static/ static/

# Create a non-root user to run the app
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

# Basic container healthcheck against the /healthz endpoint
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

# Run with gunicorn in production; main.py also supports `python main.py` for local dev
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "3", "main:app"]
