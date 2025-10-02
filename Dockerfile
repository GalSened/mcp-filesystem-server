FROM python:3.11-slim

# Security hygiene
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UVICORN_WORKERS=1 \
    MCP_FS_ROOT=/app/sandbox \
    MCP_TRANSPORT=http \
    MCP_HTTP_HOST=0.0.0.0 \
    MCP_HTTP_PORT=8080 \
    MCP_HTTP_PATH=/mcp \
    ENABLE_RUN_COMMANDS=0

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
RUN mkdir -p /app/sandbox && adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080
CMD ["python", "server.py"]
