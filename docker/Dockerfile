ARG PYTHON_VERSION=3.12

# Base image
FROM python:${PYTHON_VERSION}-alpine AS sentinela

ARG CONFIGS_FILE
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY . /app/

RUN python3 -m venv $VIRTUAL_ENV \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir poetry \
    && sh tools/install_dependencies.sh


# Sentinela dev image
FROM sentinela AS sentinela_dev

RUN sh tools/install_tests_dependencies.sh
