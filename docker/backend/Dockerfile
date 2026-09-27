FROM python:3.11-slim

# System deps: Tesseract OCR (rus+eng языковые пакеты) + libgl для OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

ENV PYTHONUNBUFFERED=1 \
    CATALOG_PATH=/app/data/catalog.csv \
    OCR_LANGS=rus+eng \
    MATCH_MIN_SCORE=55 \
    MATCH_GAP_THRESHOLD=8 \
    TOP_K=5 \
    FRONTEND_DIR=/app/frontend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
