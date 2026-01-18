# Multi-stage Dockerfile for MCP Server
# Production-grade with minimal attack surface

# Build stage
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create virtual environment
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

LABEL maintainer="engineering@example.com"
LABEL version="1.0.0"
LABEL description="Production MCP Server with Azure Workload Identity"

# Create non-root user
RUN useradd -m -u 1000 mcpserver && \
    mkdir -p /app /var/run/secrets/azure/tokens && \
    chown -R mcpserver:mcpserver /app /var/run/secrets/azure/tokens

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=mcpserver:mcpserver /opt/venv /opt/venv

# Copy application code
COPY --chown=mcpserver:mcpserver src/ ./src/

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AZURE_AUTHORITY_HOST=https://login.microsoftonline.com

# Create non-root volume mount point for Azure tokens (Workload Identity)
RUN mkdir -p /var/run/secrets/azure/tokens && \
    chown mcpserver:mcpserver /var/run/secrets/azure/tokens

# Switch to non-root user
USER mcpserver

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health/live', timeout=3.0)"

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
