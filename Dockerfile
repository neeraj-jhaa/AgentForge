# --- AgentForge : single-container image -----------------------------
FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal on purpose - no compiler toolchain needed
# for the pinned wheel versions in requirements.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY frontend ./frontend

RUN mkdir -p /app/backend/data

ENV PYTHONUNBUFFERED=1 \
    AGENTFORGE_DB=/app/backend/data/agentforge.db

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8001/api/health || exit 1

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
