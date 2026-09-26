ARG PYTHON_VERSION=3.12

ARG SENTINELA_REPO=https://github.com/GabrielSalla/sentinela
ARG SENTINELA_VERSION=0.8.8

ARG USER_CONFIG=configs.yaml


# Base image
FROM python:${PYTHON_VERSION}-alpine AS base

ARG SENTINELA_REPO
ARG SENTINELA_VERSION
ARG USER_CONFIG=configs.yaml

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    CONFIGS_FILE=configs.yaml

WORKDIR /app

RUN wget -qO- "${SENTINELA_REPO}/archive/refs/tags/${SENTINELA_VERSION}.tar.gz" \
    | tar -xz --strip-components=1 -C /app

COPY ${USER_CONFIG} /app/configs.yaml

RUN python3 -m venv $VIRTUAL_ENV \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir poetry \
    && sh tools/install_dependencies.sh


# Sentinela image
FROM python:${PYTHON_VERSION}-alpine AS sentinela

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    CONFIGS_FILE=configs.yaml

WORKDIR /app

COPY --from=base /app /app
COPY --from=base /opt /opt
COPY --from=base /etc /etc
COPY --from=base /usr /usr
