# syntax=docker/dockerfile:1
# HKU Recycling Rules Helper — single-image deploy (Render, Hugging Face Spaces
# or any Docker host). Builds the frontend, pre-builds the Chroma store and
# caches the bge-small ONNX model INTO the image, so the runtime needs no
# network and no persistent disk. No torch, so it fits a 512 MB instance.

# ---------- Stage 1: build the React frontend ----------
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
# Flask serves the bundle from the site root, so pin the base path whatever
# vite.config.ts says.
RUN npm run build -- --base=/

# ---------- Stage 2: Python runtime + RAG backend ----------
FROM python:3.13-slim AS runtime

# build-essential: in case a chromadb dependency has no wheel and compiles.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces runs the container as uid 1000. Own /app as that user so
# Chroma can open its SQLite file at runtime.
RUN useradd -m -u 1000 user
WORKDIR /app
RUN chown user:user /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application source. (data/chroma is rebuilt below; frontend/dist comes
# from Stage 1; secrets come from the environment, never baked in.)
USER user
COPY --chown=user backend/ backend/
COPY --chown=user corpus/ corpus/
COPY --chown=user scripts/ scripts/
COPY --chown=user transcription_checklist.md ./

# Serve the built frontend from Flask on a single port.
COPY --chown=user --from=frontend /build/frontend/dist frontend/dist

# Download the bge-small model and build the read-only Chroma store inside the
# image. --require-reviewed freezes the corpus (all sources must be reviewed).
ENV HF_HOME=/app/.hf_home \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PYTHONUNBUFFERED=1 \
    TRUST_PROXY_HOPS=1
RUN python scripts/ingest.py --require-reviewed

# Serve on the port the host assigns ($PORT, default 7860). The model is
# already cached, so disable any download attempt at runtime.
EXPOSE 7860
CMD ["sh", "-c", "HF_HUB_OFFLINE=1 exec flask --app backend.app run --host 0.0.0.0 --port ${PORT:-7860}"]
