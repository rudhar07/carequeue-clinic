# CareQueue API image (FastAPI + Uvicorn).
# Base pinned by tag AND digest (multi-arch index: amd64 for CI, arm64 for a Mac).
FROM python:3.13-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f

LABEL org.opencontainers.image.source="https://github.com/rudhar07/carequeue-clinic" \
      org.opencontainers.image.title="carequeue-backend" \
      org.opencontainers.image.description="CareQueue clinic appointments & patient queue API"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
# pip is only needed while building. Removing it also removes its vendored
# libraries, which image scanners would otherwise report.
RUN pip install -r requirements.txt \
 && pip uninstall -y pip \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin carequeue

COPY alembic.ini docker-entrypoint.sh ./
COPY alembic ./alembic
COPY app ./app

ARG GIT_SHA=local
ARG APP_VERSION=1.0.0
ENV GIT_SHA=${GIT_SHA} \
    APP_VERSION=${APP_VERSION}

# Numeric UID so Kubernetes can verify runAsNonRoot.
USER 10001
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

ENTRYPOINT ["./docker-entrypoint.sh"]
# One worker per container: Prometheus counters live in process memory, so
# scale with more replicas rather than more workers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header", "--no-access-log"]
