# Development
build-dev:
	docker compose -f docker-compose-dev.yaml build sentinela-dev

pull-dev:
	docker compose -f docker-compose-dev.yaml pull --quiet postgres motoserver

migrate-dev:
	docker compose -f docker-compose-dev.yaml run --rm --service-ports sentinela-dev alembic upgrade head

run-dev:
	docker compose -f docker-compose-dev.yaml up sentinela-dev

run-shell-dev:
	docker compose -f docker-compose-dev.yaml run --rm --service-ports sentinela-dev /bin/sh

test-dev:
	docker compose -f docker-compose-dev.yaml run --rm sentinela-dev pytest

down-dev:
	docker compose -f docker-compose-dev.yaml down

# Local development setup
build-local:
	docker compose -f docker-compose-local.yaml build sentinela-local

migrate-local:
	docker compose -f docker-compose-local.yaml run --rm --service-ports sentinela-local alembic upgrade head

run-local:
	docker compose -f docker-compose-local.yaml up sentinela-local

down-local:
	docker compose -f docker-compose-local.yaml down

# Scalable setup for production-like environment
build-scalable:
	docker compose -f docker-compose-scalable.yaml build sentinela-controller

migrate-scalable:
	docker compose -f docker-compose-scalable.yaml run --rm --service-ports sentinela-controller alembic upgrade head

run-scalable:
	docker compose -f docker-compose-scalable.yaml up sentinela-controller sentinela-executor

down-scalable:
	docker compose -f docker-compose-scalable.yaml down

# Development utilities
linter:
	docker compose -f docker-compose-dev.yaml run --rm --no-deps sentinela-dev ruff check
	docker compose -f docker-compose-dev.yaml run --rm --no-deps sentinela-dev ruff format --check --diff

mypy:
	docker compose -f docker-compose-dev.yaml run --rm --no-deps sentinela-dev mypy --install-types --non-interactive
