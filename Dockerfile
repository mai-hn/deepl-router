# Build the React management console first.
FROM node:24-bookworm-slim AS frontend-build

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# Keep the runtime image focused on the Python API and compiled frontend assets.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEEPL_ROUTER_DB=/data/router.db

WORKDIR /app

COPY pyproject.toml ./
COPY deepl_router/ ./deepl_router/
RUN python -m pip install --upgrade pip && python -m pip install .

COPY --from=frontend-build /build/frontend/dist ./frontend/dist

RUN mkdir -p /data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/api/health', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "deepl_router.app:app", "--host", "0.0.0.0", "--port", "8080"]
