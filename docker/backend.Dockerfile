# Backend image: FastAPI + inference pipeline + replay generator.
# CPU-only; installs the CPU PyTorch wheel to keep the image small.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching).
COPY requirements.txt .
# CPU torch wheel keeps the image lean; the rest from PyPI.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

# App source.
COPY core ./core
COPY features ./features
COPY ml ./ml
COPY sensor ./sensor
COPY replay ./replay
COPY backend ./backend
COPY configs ./configs
COPY models ./models
COPY artifacts ./artifacts

EXPOSE 8000

# Default: run the API + inference loop. Override `command` for replay/train.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
