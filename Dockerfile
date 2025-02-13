ARG PYTHON_VERSION=3.12

# Base image
FROM python:${PYTHON_VERSION}-alpine AS base

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY . /app/

RUN python3 -m venv $VIRTUAL_ENV \
    && pip install --no-cache-dir --upgrade pip \
    && pip install poetry --no-cache-dir \
    && sh tools/install_dependencies.sh


# Sentinela image
FROM python:${PYTHON_VERSION}-alpine AS sentinela

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=base /app /app
COPY --from=base /opt /opt


# Base dev image
FROM base AS base_dev

RUN poetry install --only dev


# Sentinela dev image
FROM python:${PYTHON_VERSION}-alpine AS sentinela_dev

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=base_dev /app /app
COPY --from=base_dev /opt /opt
