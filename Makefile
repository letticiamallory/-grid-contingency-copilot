.PHONY: up down migrate ingest lint test eval-fake eval-calibrate eval audit-verify

up:
	docker compose up -d db

down:
	docker compose down

migrate:
	uv run python -m copilot.adapters.outbound.postgres.migrate

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src

test:
	uv run pytest

# Alvos abaixo ainda nao implementados (ver docs/05-roadmap.md)
ingest:
	uv run python -m copilot.adapters.inbound.cli.ingest $(ARGS)

eval-fake:
	@echo "not implemented yet (M4)"; exit 1

eval-calibrate:
	@echo "not implemented yet (M4)"; exit 1

eval:
	@echo "not implemented yet (M4)"; exit 1

audit-verify:
	uv run python -m copilot.adapters.inbound.cli.audit_verify
