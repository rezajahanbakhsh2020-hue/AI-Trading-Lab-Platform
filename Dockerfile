# Multi-stage production Dockerfile for AI-Trading-Lab-Platform

# Stage 1: Build Vite/React SPA Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Production Application Runtime
FROM python:3.11-slim AS runtime

# Security hardening: Non-root user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy application source code
COPY src/ ./src/

# Copy compiled frontend SPA build from Stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Setup persistence directory with correct ownership
RUN mkdir -p /app/.data && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

ENV APP_ENV=production \
    PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/liveness')" || exit 1

CMD ["python", "-m", "src.platform.server"]
