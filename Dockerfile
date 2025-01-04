FROM python:3.12-alpine AS sentinela

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apk add curl \
    && python3 -m venv $VIRTUAL_ENV \
    && pip install --upgrade pip \
    && pip install poetry --no-cache-dir

COPY . /app/

RUN poetry install --no-root --only main \
    && poetry cache clear --no-interaction --all .


FROM sentinela AS sentinela_dev

RUN poetry install --no-root \
    && poetry cache clear --no-interaction --all .
