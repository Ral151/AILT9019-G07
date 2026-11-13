# syntax=docker/dockerfile:1
# HKU Recycling Rules Helper — single-image deploy (Hugging Face Spaces / any
# Docker host). Builds the frontend, installs CPU-only torch, pre-builds the
# Chroma store and caches the bge-small model INTO the image, so the runtime
# needs no network and no persistent disk.

# ---------- Stage 1: build the React frontend ----------
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python runtime + RAG backend ----------
FROM python:3.13-slim AS runtime

# build-essential: some chromadb/sentence-transformers deps compile on install.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# IMPORTANT: on Linux, a plain `pip install torch` pulls the multi-GB CUDA
# build. Install the CPU wheel first, then install the rest of the pinned
# requirements with the torch line removed — otherwise pip re-resolves
# `torch==2.14.1` to the PyPI CUDA wheel and overwrites the CPU build.
RUN pip install --no-cache-dir torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt backend/requirements.txt
RUN grep -v -E '^torch' backend/requirements.txt > /tmp/requirements-notorch.txt \
    && pip install --no-cache-dir -r /tmp/requirements-notorch.txt

# Copy application source. (data/chroma is rebuilt below; frontend/dist comes
# from Stage 1; secrets come from the environment, never baked in.)
COPY backend/ backend/
COPY corpus/ corpus/
COPY scripts/ scripts/
COPY transcription_checklist.md ./

# Serve the built frontend from Flask on a single port.
COPY --from=frontend /build/frontend/dist frontend/dist

# Download the bge-small model and build the read-only Chroma store inside the
# image. --require-reviewed freezes the corpus (all sources must be reviewed).
ENV HF_HOME=/app/.hf_home \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PYTHONUNBUFFERED=1
RUN python scripts/ingest.py --require-reviewed

# Serve on the port Hugging Face assigns (default 7860). The model is already
# cached, so disable any download attempt at runtime.
EXPOSE 7860
CMD ["sh", "-c", "TRANSFORMERS_OFFLINE=1 exec flask --app backend.app run --host 0.0.0.0 --port ${PORT:-7860}"]
