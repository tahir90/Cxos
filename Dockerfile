FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ src/

# Retries and timeout help with flaky network during Docker builds
ENV PIP_RETRIES=5
ENV PIP_TIMEOUT=120

RUN pip install --upgrade pip && \
    pip install --no-cache-dir --retries 5 --timeout 120 -e "." && \
    pip install --no-cache-dir --retries 5 --timeout 120 gunicorn

# Pre-download ChromaDB ONNX model so startup is instant
RUN python -c "import chromadb; c=chromadb.Client(); c.get_or_create_collection('warmup'); c.delete_collection('warmup')"

COPY examples/ examples/

RUN mkdir -p /app/.cxo_data

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD ["/bin/sh", "-c", "python -m uvicorn agentic_cxo.api.server:app --host 0.0.0.0 --port ${PORT}"]
