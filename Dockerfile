# syntax=docker/dockerfile:1

FROM node:24-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production
WORKDIR /app
RUN useradd --system --uid 10001 --no-create-home appuser
COPY apps/api/requirements.txt .
RUN pip install -r requirements.txt
COPY apps/api/app ./app
COPY --from=web /web/dist ./static
USER appuser
EXPOSE 4000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:4000/health', timeout=4).status != 200)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 4000 --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS:-*}\" --no-server-header"]
