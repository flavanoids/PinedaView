# SPDX-License-Identifier: Apache-2.0
# syntax=docker/dockerfile:1

# ── build the web client ─────────────────────────────────────────────────────
FROM node:22-alpine AS web
RUN corepack enable
WORKDIR /app
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json ./
COPY packages ./packages
COPY web ./web
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @pinedaview/client build

# ── assemble the Python app ──────────────────────────────────────────────────
FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN useradd --system --uid 10001 --create-home --home-dir /home/pineda pineda \
    && mkdir -p /data /etc/pineda-web && chown -R pineda:pineda /data

WORKDIR /app
COPY core ./core
COPY --from=web /app/web/dist ./core/src/pinedaview/webroot
RUN uv pip install --system --no-cache ./core

USER pineda
ENV PINEDA_API__HOST=0.0.0.0 \
    PINEDA_API__PORT=8090 \
    PINEDA_STATE_DIR=/data/state \
    PINEDA_PHOTOS_DIR=/data/photos \
    PINEDA_CARDS_DIR=/data/cards \
    PINEDA_API__DB_PATH=/data/state/pineda.db \
    PINEDA_CONFIG_FILE=/etc/pineda-web/config.toml

EXPOSE 8090
VOLUME ["/data", "/etc/pineda-web"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/api/health').status==200 else 1)"]

ENTRYPOINT ["pineda-web", "serve"]
