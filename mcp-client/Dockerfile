# Multi-stage Dockerfile for MCP Client

FROM python:3.11-slim as builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

LABEL maintainer="engineering@example.com"
LABEL version="1.0.0"
LABEL description="MCP Client with Azure Workload Identity"

RUN useradd -m -u 1000 mcpclient && \
    mkdir -p /app /var/run/secrets/azure/tokens && \
    chown -R mcpclient:mcpclient /app /var/run/secrets/azure/tokens

WORKDIR /app

COPY --from=builder --chown=mcpclient:mcpclient /opt/venv /opt/venv
COPY --chown=mcpclient:mcpclient src/ ./src/

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AZURE_AUTHORITY_HOST=https://login.microsoftonline.com

USER mcpclient

EXPOSE 8001

CMD ["python", "-m", "src.main"]
