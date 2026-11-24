FROM python:3.12-slim

# Small, predictable memory use on 512 MB instances: one worker, single-threaded
# BLAS/OpenMP, fewer malloc arenas.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2 \
    PORT=8080 \
    BASE_PATH=""

WORKDIR /app

COPY requirements.txt .
RUN pip install --timeout 120 --retries 10 -r requirements.txt

COPY app ./app
COPY data ./data

RUN useradd --create-home --uid 10001 themis
USER themis

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
