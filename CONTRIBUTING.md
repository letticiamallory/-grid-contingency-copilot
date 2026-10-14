# Contribuindo

Projeto de portfólio mantido por uma pessoa. Sugestões e issues são bem-vindas; antes de enviar conteúdo, leia a política de dados em `docs/adr/ADR-007-dados-sinteticos-politica-de-conteudo.md`. Não envie procedimentos, dados ou nomes de organizações reais.

## Commits

Conventional Commits em inglês, no imperativo:

```text
<type>(<scope>): <summary>
```

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `perf`. Escopos sugeridos: `domain`, `app`, `api`, `retriever`, `llm`, `audit`, `eval`, `kb`, `docs`.

Exemplos:

```text
feat(domain): verify citations against retrieved chunks
fix(audit): serialize hash chain writes per event
docs(adr): record decision on orchestration
```

Mudança incompatível: `!` após o escopo ou rodapé `BREAKING CHANGE:`.

## Branches

- `main`: sempre verde; recebe apenas merges por pull request.
- `feat/<assunto>`, `fix/<assunto>`, `docs/<assunto>`: ramos curtos a partir de `main`.
- Pull requests pequenos, com a CI verde e uma linha sobre o que mudou nos documentos, se mudou.
- Mudança de decisão arquitetural: novo ADR (ou ADR atualizado com status e data), no mesmo PR.

## Rodando os testes

```bash
docker compose up -d db        # Postgres + pgvector
pip install -e ".[dev]"        # ou: uv sync
make lint                      # ruff + mypy
make test                      # unitários + integração + contrato
make eval-fake                 # avaliação determinística, sem custo
```

`make eval` usa modelos reais e créditos do OpenRouter; não roda na CI. Rodar antes de alterar prompt, modelo ou limiar de recusa, e versionar o relatório em `eval/reports/`.

## Conteúdo da base de conhecimento

Siga o template e o checklist de `docs/04-base-de-conhecimento.md`. Um teste da CI falha se faltar `PO-FICT-`, `ficticio: true` ou o aviso.
