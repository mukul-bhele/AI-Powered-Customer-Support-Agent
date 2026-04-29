# ── Base image ────────────────────────────────────────────────────────────────
# Python 3.11 slim keeps the image small (~150 MB base vs ~900 MB full)
FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
# build-essential  → needed to compile some Python packages (e.g. onnxruntime)
# curl             → used by the deploy script to health-check the API
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
# Copy requirements first so Docker can cache this layer.
# The layer is only rebuilt when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY customer_support_agent/ ./customer_support_agent/
COPY knowledge_base/         ./knowledge_base/
COPY dashboard.py            ./dashboard.py
# .env is NOT baked into the image — it is mounted at runtime via docker-compose

# ── Persistent data directory ─────────────────────────────────────────────────
# SQLite database and ChromaDB files are stored here.
# In docker-compose this folder is mounted as a named volume so data
# survives container restarts and rebuilds.
RUN mkdir -p /app/data

# ── Default command ───────────────────────────────────────────────────────────
# Overridden per-service in docker-compose.yml
CMD ["uvicorn", "customer_support_agent.api.app_factory:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000"]
