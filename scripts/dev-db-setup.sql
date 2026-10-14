-- Prepara o Postgres NATIVO para desenvolvimento local (alternativa ao docker compose).
-- Rodar uma vez, como superusuario, DEPOIS de instalar o pgvector no servidor:
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -f scripts/dev-db-setup.sql
-- A senha abaixo e so para desenvolvimento local e combina com .env.example.

CREATE ROLE copilot LOGIN PASSWORD 'copilot';
CREATE DATABASE copilot OWNER copilot;

\connect copilot
-- Precisa de superusuario; por isso e feito aqui e nao pela migration do usuario copilot.
CREATE EXTENSION IF NOT EXISTS vector;
