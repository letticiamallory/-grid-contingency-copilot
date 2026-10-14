# 05 - Roadmap

Premissa: 20 h de desenvolvimento no total, 5 h por semana (cerca de 4 semanas). As estimativas são minhas e provavelmente otimistas: a escrita dos procedimentos e dos cenários costuma custar mais que o previsto. Se o orçamento apertar, corte nesta ordem: M5 polimento, depois parte dos cenários (mantendo mínimo de 20 categorias), nunca a verificação de citação nem a auditoria.

## Versão mínima (20 h)

### M0 - Fundação (2 h)
- [x] Repositório, estrutura de pastas, `pyproject`, `ruff`, `pytest`
- [x] `docker-compose.yml` com Postgres + pgvector; migration inicial
- [x] `.env.example`, `Makefile` com alvos vazios
- [x] CI com lint + testes (ainda trivial)
- [x] LICENSE (MIT), aviso de dados sintéticos

### M1 - Base de conhecimento e ingestão (4 h)
- [ ] 10 procedimentos fictícios (3 h, ver `04-base-de-conhecimento.md`)
- [x] Parser de front-matter e divisão em chunks
- [x] Teste de CI para marcadores de conteúdo fictício
- [ ] Ingestão com embeddings e `tsvector` (1 h)
- [ ] Decisão do modelo de embedding (OpenRouter ou local), registrada no ADR-002

### M2 - Núcleo do fluxo (4 h)
- [x] Modelos do domínio, `citation.py` com testes de paráfrase, acento e espaço
- [x] Portas e `FakeLLM`, repositórios em memória
- [x] Caso de uso `GenerateSuggestion` com as três causas de recusa
- [ ] Retriever híbrido (RRF) e filtro de procedimentos revogados
- [x] Adaptador OpenRouter (timeout, 1 retry, breaker, fallback) e prompt v1; só testado com transporte simulado

### M3 - API, decisão e auditoria (3 h)
- [x] Rotas de eventos, sugestões, decisão e auditoria
- [x] `RecordDecision` com regra de estados e `CHECK` no banco
- [x] Auditoria encadeada com trigger bloqueando `UPDATE/DELETE`; `audit-verify`
- [x] Testes de integração (Postgres real) e teste de contrato do OpenAPI

### M4 - Avaliação (5 h)
- [x] Formato YAML e carregador; 24 categorias, 73 cenários (rascunhos; revisão da autora pendente)
- [x] Cálculo das métricas e bootstrap
- [x] Calibração do limiar no `calibration`
- [ ] Rodada real com 2 modelos x com/sem RAG, mais baseline lexical
- [x] Relatório em `eval/reports/` e `make eval-fake` na CI

### M5 - README e publicação (2 h)
- [ ] README com resultados reais no lugar do placeholder
- [ ] Revisão do checklist de política de conteúdo (ADR-007)
- [ ] Verificar que não há segredos nem histórico sensível no repositório
- [ ] `docs/` revisados contra o que foi realmente implementado (ajustar ADRs e escopo)

**Ponto mínimo para divulgar: fim do M5**, com M4 contendo ao menos uma rodada real da avaliação. Um repositório sem resultados medidos perde o argumento principal. Se faltar tempo, é melhor divulgar com 40 cenários e resultados honestos do que com 90 cenários e sem rodada.

Total: 20 h, sem folga. Trate a primeira semana de M0 e M1 como termômetro: se levarem mais de 7 h, replanejar cortando cenários e procedimentos.

## Extras opcionais (depois da divulgação)

| Extra | Estimativa | Observação |
|---|---|---|
| Circuit breaker e fallback (ADR-005), com testes de relógio falso | 2 h | Os critérios de RNF-03 só ficam completos com isso. O mínimo tem apenas timeout e retry. |
| Juiz LLM de fidelidade semântica, com 20 julgamentos conferidos | 3 h | Só publicar se a concordância for medida. |
| Orquestração em LangGraph com reformulação da busca, e comparação com o fluxo simples | 4 h | Ver ADR-004; o extra só se justifica se houver ciclo de busca. |
| Ancoragem do hash final da auditoria (ex.: publicado em arquivo versionado) | 1 h | Reduz a limitação do ADR-006. |
| Revisão dos cenários por uma segunda pessoa | variável | Melhor ganho de credibilidade por hora. |
| Página HTML simples para revisar sugestões | 2 h | Só se o Swagger incomodar na demonstração. |
| Redis | - | Não há caso de uso que o justifique hoje; não fazer sem uma necessidade medida. |

## Observação sobre consistência

O escopo (RNF-03) e o ADR-005 listam circuit breaker e fallback como parte do desenho, mas o roadmap os coloca fora das 20 h. Essa diferença é intencional e precisa de uma decisão sua: ou mover os 2 h para dentro do mínimo (e cortar cenários), ou ajustar RNF-03 para refletir apenas timeout e retry no mínimo.

## Estado em 14/10/2026

Concluído sem chave do OpenRouter: M0, M2 (exceto retriever híbrido e verificação do adaptador contra a API real), M3, parte do M4 (cenários, métricas, calibração, `eval-fake`) e o circuit breaker com fallback (antes um extra). Pendente: embeddings e retriever híbrido, prompt v1 validado com modelo real, rodada real da avaliação, 30% dos cenários escritos antes dos procedimentos (ADR-008), reescrita dos procedimentos pela autora, M5.
