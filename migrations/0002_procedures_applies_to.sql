-- Persiste o front-matter `applies_to` dos procedimentos (docs/04-base-de-conhecimento.md).
-- Ainda nao e usado na recuperacao; como o evento vira consulta e uma decisao em aberto.
ALTER TABLE procedures ADD COLUMN applies_to text[] NOT NULL DEFAULT '{}';
