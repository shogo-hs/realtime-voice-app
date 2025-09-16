# syntax=docker/dockerfile:1.6

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    libportaudio2 \
    libasound2 \
    libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv

RUN uv sync --frozen --no-dev

COPY realtime_voice ./realtime_voice
COPY README.md AGENTS.md ./
COPY realtime_voice/web ./realtime_voice/web

EXPOSE 8000

ENV WEB_SERVER_HOST=0.0.0.0 \
    WEB_SERVER_PORT=8000

ENTRYPOINT ["uv", "run", "python", "-m", "realtime_voice.webserver"]
