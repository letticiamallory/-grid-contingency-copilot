.PHONY: up down migrate ingest lint test eval-fake eval-calibrate eval audit-verify
RETRIEVAL ?= lexical

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

ingest:
	uv run python -m copilot.adapters.inbound.cli.ingest $(ARGS)

# Avaliacao (M4). eval-fake usa o LLM de eco: mede recuperacao, recusa e encanamento, nao qualidade.
eval-calibrate:
	uv run python -m copilot.adapters.inbound.cli.evaluate calibrate --llm echo --retrieval $(RETRIEVAL)

eval-fake:
	uv run python -m copilot.adapters.inbound.cli.evaluate run --llm echo --split test --retrieval $(RETRIEVAL)

eval:
	@echo "LLM real ainda nao implementado (depende de OPENROUTER_API_KEY e do adaptador, ADR-005)"; exit 1

audit-verify:
	uv run python -m copilot.adapters.inbound.cli.audit_verify
