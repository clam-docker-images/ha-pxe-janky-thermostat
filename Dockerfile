ARG BASE_IMAGE=debian:trixie-slim

FROM ${BASE_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JANKY_CONFIG_FILE=/config/config.json

WORKDIR /app

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential ca-certificates git python3 python3-pip python3-venv; \
    rm -rf /var/lib/apt/lists/*

COPY janky-thermostat/requirements.txt /tmp/requirements.txt

RUN set -eux; \
    python3 -m venv /opt/venv; \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel; \
    /opt/venv/bin/pip install -r /tmp/requirements.txt

COPY janky-thermostat/ /app/

FROM ${BASE_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    JANKY_CONFIG_FILE=/config/config.json \
    PATH=/opt/venv/bin:${PATH}

WORKDIR /app

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates python3; \
    rm -rf /var/lib/apt/lists/*; \
    mkdir -p /config

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

CMD ["python", "-u", "/app/main.py"]
