# 01 - Arquitetura

## Contexto (C4 nível 1)

```mermaid
C4Context
    title Contexto - Grid Contingency Copilot
    Person(op, "Operador (simulado)", "Registra eventos, revisa sugestões, aprova ou rejeita")
    Person(av, "Avaliador", "Roda a avaliação e inspeciona a auditoria")
    System(sys, "Grid Contingency Copilot", "Sugere passos de resposta com citação obrigatória, recusa quando não há procedimento")
    System_Ext(llm, "OpenRouter", "Acesso a modelos de linguagem e embeddings")
    Rel(op, sys, "Usa", "HTTP/Swagger")
    Rel(av, sys, "Executa avaliação", "CLI")
    Rel(sys, llm, "Gera texto e embeddings", "HTTPS")
```

## Contêineres (C4 nível 2)

```mermaid
C4Container
    title Contêineres
    Person(op, "Operador")
    Person(av, "Avaliador")
    System_Boundary(s, "Grid Contingency Copilot") {
        Container(api, "API", "Python 3.12, FastAPI", "Casos de uso, validação de citação, aprovação")
        Container(cli, "CLI de ingestão e avaliação", "Python", "Indexa procedimentos, roda cenários, gera relatório")
        ContainerDb(db, "PostgreSQL + pgvector", "PostgreSQL 16", "Procedimentos, chunks, eventos, sugestões, decisões, auditoria")
    }
    System_Ext(or, "OpenRouter", "LLM e embeddings")
    Rel(op, api, "HTTP JSON")
    Rel(av, cli, "Comandos make")
    Rel(api, db, "SQL")
    Rel(cli, db, "SQL")
    Rel(api, or, "HTTPS, com circuit breaker")
    Rel(cli, or, "HTTPS")
```

Não há Redis nem fila no desenho mínimo. A geração é síncrona, porque uma sugestão leva segundos e o volume é de um operador.

## Fluxo principal

```mermaid
sequenceDiagram
    actor Op as Operador
    participant API
    participant UC as Caso de uso GenerateSuggestion
    participant R as Retriever (pgvector + FTS)
    participant L as LLM (OpenRouter, com breaker)
    participant V as CitationValidator
    participant A as Auditoria

    Op->>API: POST /events
    API->>A: EVENT_RECEIVED
    Op->>API: POST /events/{id}/suggestions
    API->>UC: executar(event)
    UC->>R: buscar(event, k=6)
    R-->>UC: chunks + scores
    UC->>A: RETRIEVAL_DONE
    alt melhor score abaixo do limiar
        UC->>A: REFUSED(no_applicable_procedure)
        UC-->>API: Suggestion(status=refused)
    else há candidatos
        UC->>L: prompt (evento + chunks), saída JSON estruturada
        L-->>UC: passos com chunk_id + trecho citado, ou recusa
        UC->>A: LLM_CALLED(modelo, versão do prompt)
        UC->>V: validar cada citação contra o texto do chunk
        V-->>UC: passos válidos / descartados
        alt nenhum passo válido
            UC->>A: REFUSED(no_valid_citation)
        else
            UC->>A: SUGGESTION_CREATED
        end
        UC-->>API: Suggestion
    end
    API-->>Op: sugestão (pending_review) ou recusa
    Op->>API: POST /suggestions/{id}/decision (approve|reject, justificativa)
    API->>A: DECISION_RECORDED
    API-->>Op: 200
```

## Estrutura de pastas (hexagonal)

```text
grid-contingency-copilot/
  src/copilot/
    domain/                  # sem I/O, sem frameworks
      models.py              # Event, Procedure, Chunk, Suggestion, Step, Citation, Decision
      rules.py               # estados válidos, regra "sem decisão humana não há aprovação"
      citation.py            # normalização e checagem literal do trecho
    application/
      ports.py               # Protocols: LLMPort, EmbedderPort, RetrieverPort, *Repository, AuditLog, Clock
      use_cases/
        register_event.py
        generate_suggestion.py
        record_decision.py
        get_audit_trail.py
      prompts/               # prompts versionados (v1.md, v2.md)
    adapters/
      inbound/
        http/                # FastAPI: routers, schemas, mapeamento de erros
        cli/                 # ingest, eval
      outbound/
        postgres/            # repositórios, retriever híbrido, auditoria encadeada
        llm/                 # OpenRouter client, circuit breaker, fallback
        fakes/               # FakeLLM, FakeEmbedder, repositórios em memória
    config.py                # settings por variável de ambiente
    main.py                  # composição (wiring)
  knowledge_base/            # procedimentos fictícios em Markdown
  eval/
    scenarios/*.yaml
    run_eval.py
    reports/
  migrations/                # SQL versionado (Alembic ou arquivos numerados)
  tests/
    unit/                    # domain + application com fakes
    integration/             # Postgres real (testcontainers ou service da CI)
  docs/
  docker-compose.yml
  Makefile
```

Regra de dependência: `domain` não importa nada de fora; `application` importa só `domain`; `adapters` importam as duas e implementam as portas; `main.py` é o único lugar que conhece as implementações concretas.

## Modelo de dados

```mermaid
erDiagram
    PROCEDURE ||--o{ CHUNK : "dividido em"
    EVENT ||--o{ SUGGESTION : "gera"
    SUGGESTION ||--o{ STEP : "contém"
    STEP ||--|{ CITATION : "cita"
    CHUNK ||--o{ CITATION : "é citado em"
    SUGGESTION ||--o| DECISION : "recebe"
    EVENT ||--o{ AUDIT_LOG : "registra"

    PROCEDURE {
        text code PK "ex.: PO-FICT-014"
        text title
        text version
        text content_hash
        timestamptz ingested_at
    }
    CHUNK {
        uuid id PK
        text procedure_code FK
        text section
        text text
        vector embedding "dimensão conforme modelo"
        tsvector tsv
    }
    EVENT {
        uuid id PK
        text type
        text element
        timestamptz occurred_at
        jsonb attributes
        text reported_by
    }
    SUGGESTION {
        uuid id PK
        uuid event_id FK
        text status "pending_review | refused | approved | rejected"
        text refusal_reason "nullable"
        text model
        text prompt_version
        jsonb retrieval "ids e scores"
        timestamptz created_at
    }
    STEP {
        uuid id PK
        uuid suggestion_id FK
        int position
        text instruction
    }
    CITATION {
        uuid id PK
        uuid step_id FK
        uuid chunk_id FK
        text quote "trecho literal"
    }
    DECISION {
        uuid suggestion_id PK, FK
        text outcome "approve | reject"
        text justification
        text decided_by
        timestamptz decided_at
    }
    AUDIT_LOG {
        bigserial seq PK
        uuid event_id FK
        text kind
        jsonb payload
        text prev_hash
        text hash
        timestamptz at
    }
```

Observações:

- `SUGGESTION.status` só chega a `approved` ou `rejected` via `DECISION`. Um `CHECK` e o caso de uso garantem isso.
- `AUDIT_LOG` recebe apenas `INSERT`. Os detalhes estão no ADR-006.
- `PROCEDURE.version` e `content_hash` permitem saber, na auditoria, qual texto exato foi citado.
