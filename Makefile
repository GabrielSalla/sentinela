ARGS = $(filter-out $@,$(MAKECMDGOALS))

.ONESHELL:
# Getting the sentinela-dev container id to execute commands in it if it's already running
DEV_CONTAINER_ID = $$(docker ps -q --filter "name=sentinela-dev" | head -n 1)

# Docker compose files for different environments
DOCKER_COMPOSE_FILE_DEV = ./docker/docker-compose-dev.yaml
DOCKER_COMPOSE_FILE_LOCAL = ./docker/docker-compose-local.yaml
DOCKER_COMPOSE_FILE_SCALABLE = ./docker/docker-compose-scalable.yaml

# Environment variable + docker compose command
DOCKER_COMPOSE = docker compose --project-directory .
DOCKER_COMPOSE_DEV = COMPOSE_FILE=$(DOCKER_COMPOSE_FILE_DEV) $(DOCKER_COMPOSE)
DOCKER_COMPOSE_LOCAL = COMPOSE_FILE=$(DOCKER_COMPOSE_FILE_LOCAL) $(DOCKER_COMPOSE)
DOCKER_COMPOSE_SCALABLE = COMPOSE_FILE=$(DOCKER_COMPOSE_FILE_SCALABLE) $(DOCKER_COMPOSE)

# Development
build-dev:
	@$(DOCKER_COMPOSE_DEV) build sentinela-dev

pull-dev:
	@$(DOCKER_COMPOSE_DEV) pull --quiet postgres motoserver

migrate-dev:
	@$(DOCKER_COMPOSE_DEV) run --rm --service-ports sentinela-dev alembic upgrade head

run-dev:
	@$(DOCKER_COMPOSE_DEV) up sentinela-dev

run-shell-dev:
	@$(DOCKER_COMPOSE_DEV) run --rm --service-ports sentinela-dev /bin/sh

test-dev:
	@container_id="$(DEV_CONTAINER_ID)"
	if [ -n "$$container_id" ]; then
		docker exec -i "$$container_id" pytest $(ARGS)
	else
		$(DOCKER_COMPOSE_DEV) run --rm sentinela-dev pytest $(ARGS)
	fi

down-dev:
	@$(DOCKER_COMPOSE_DEV) down

# Local development setup
build-local:
	@$(DOCKER_COMPOSE_LOCAL) build sentinela-local

migrate-local:
	@$(DOCKER_COMPOSE_LOCAL) run --rm --service-ports sentinela-local alembic upgrade head

run-local:
	@$(DOCKER_COMPOSE_LOCAL) up sentinela-local

down-local:
	@$(DOCKER_COMPOSE_LOCAL) down

# Scalable setup for production-like environment
build-scalable:
	@$(DOCKER_COMPOSE_SCALABLE) build sentinela-controller

migrate-scalable:
	@$(DOCKER_COMPOSE_SCALABLE) run --rm --service-ports sentinela-controller alembic upgrade head

run-scalable:
	@$(DOCKER_COMPOSE_SCALABLE) up sentinela-controller sentinela-executor

down-scalable:
	@$(DOCKER_COMPOSE_SCALABLE) down

# Development utilities
linter:
	@set -e
	container_id="$(DEV_CONTAINER_ID)"
	if [ -n "$$container_id" ]; then
		docker exec -i "$$container_id" ruff check $(ARGS)
		docker exec -i "$$container_id" ruff format --check --diff $(ARGS)
	else
		$(DOCKER_COMPOSE_DEV) run --rm --no-deps sentinela-dev ruff check $(ARGS)
		$(DOCKER_COMPOSE_DEV) run --rm --no-deps sentinela-dev ruff format --check --diff $(ARGS)
	fi

mypy:
	@container_id="$(DEV_CONTAINER_ID)"
	if [ -n "$$container_id" ]; then
		docker exec -i "$$container_id" mypy --install-types --non-interactive $(ARGS)
	else
		$(DOCKER_COMPOSE_DEV) run --rm --no-deps sentinela-dev mypy --install-types --non-interactive $(ARGS)
	fi
