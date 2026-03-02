# Stage 1: Builder
FROM python:3.12-bookworm AS builder

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime
FROM python:3.12-slim-bookworm

# Runtime deps for lxml and pymupdf
RUN apt-get update && \
    apt-get install -y --no-install-recommends libxml2 libxslt1.1 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY src/ /app/src/

WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "transform_agent.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
