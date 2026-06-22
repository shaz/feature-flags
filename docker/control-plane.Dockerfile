# Build context is the repo root (see control-plane/Makefile `build`).
FROM python:3.12-slim

WORKDIR /app

COPY control-plane/pyproject.toml ./
COPY control-plane/app ./app
COPY control-plane/config ./config
COPY migrations ./migrations
RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
