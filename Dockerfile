FROM python:3.9-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and templates
COPY app.py .
COPY templates/ templates/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:9090/status || exit 1

# Expose port
EXPOSE 9090

# Use Gunicorn with eventlet worker for Flask-SocketIO with access logging
CMD ["gunicorn", "--worker-class", "eventlet", "--workers", "1", "--bind", "0.0.0.0:9090", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "app:app"] 