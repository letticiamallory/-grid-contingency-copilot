-- Schema inicial conforme docs/01-arquitetura.md (modelo de dados) e ADR-002/003/006.
-- Embedding: openai/text-embedding-3-small -> 1536 dimensoes (trocar o modelo exige nova migration).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE procedures (
    code           text PRIMARY KEY,
    title          text NOT NULL,
    version        text NOT NULL,
    status         text NOT NULL DEFAULT 'vigente' CHECK (status IN ('vigente', 'revogado')),
    content_hash   text NOT NULL,
    embedding_model text,
    ingested_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    procedure_code text NOT NULL REFERENCES procedures (code) ON DELETE CASCADE,
    section        text NOT NULL,
    text           text NOT NULL,
    embedding      vector(1536),
    tsv            tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', text)) STORED
);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
-- Sem indice ANN de proposito: com poucas centenas de linhas a varredura exata e melhor (ADR-002).

CREATE TABLE events (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type        text NOT NULL,
    element     text NOT NULL,
    occurred_at timestamptz NOT NULL,
    attributes  jsonb NOT NULL DEFAULT '{}',
    reported_by text NOT NULL
);

CREATE TABLE suggestions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id       uuid NOT NULL REFERENCES events (id),
    status         text NOT NULL
                   CHECK (status IN ('pending_review', 'refused', 'approved', 'rejected')),
    refusal_reason text
                   CHECK (refusal_reason IN
                          ('no_applicable_procedure', 'model_declined', 'no_valid_citation')),
    model          text,
    prompt_version text,
    retrieval      jsonb NOT NULL DEFAULT '[]',
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT refusal_reason_iff_refused
        CHECK ((status = 'refused') = (refusal_reason IS NOT NULL))
);
CREATE INDEX suggestions_event_idx ON suggestions (event_id);

CREATE TABLE steps (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    suggestion_id uuid NOT NULL REFERENCES suggestions (id),
    position      int NOT NULL CHECK (position >= 1),
    instruction   text NOT NULL,
    UNIQUE (suggestion_id, position)
);

CREATE TABLE citations (
    id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    step_id  uuid NOT NULL REFERENCES steps (id),
    chunk_id uuid NOT NULL REFERENCES chunks (id),
    quote    text NOT NULL
);

CREATE TABLE decisions (
    suggestion_id uuid PRIMARY KEY REFERENCES suggestions (id),
    outcome       text NOT NULL CHECK (outcome IN ('approve', 'reject')),
    justification text,
    decided_by    text NOT NULL,
    decided_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT reject_requires_justification
        CHECK (outcome <> 'reject' OR (justification IS NOT NULL AND length(trim(justification)) > 0))
);

CREATE TABLE audit_log (
    seq       bigserial PRIMARY KEY,
    event_id  uuid NOT NULL REFERENCES events (id),
    kind      text NOT NULL CHECK (kind IN (
                  'EVENT_RECEIVED', 'RETRIEVAL_DONE', 'LLM_CALLED', 'CITATIONS_VALIDATED',
                  'SUGGESTION_CREATED', 'REFUSED', 'DECISION_RECORDED')),
    payload   jsonb NOT NULL,
    prev_hash text NOT NULL,
    hash      text NOT NULL,
    at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_event_idx ON audit_log (event_id, seq);

-- Auditoria so de acrescimo (ADR-006). Nao protege contra superusuario do banco.
CREATE FUNCTION audit_log_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only (% blocked)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_block_mutation();

CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION audit_log_block_mutation();
