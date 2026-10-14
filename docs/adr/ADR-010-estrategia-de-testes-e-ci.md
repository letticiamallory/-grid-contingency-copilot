# ADR-010: Estratégia de testes (unitários, integração, avaliação) e CI

- Status: aceito
- Data: a preencher

## Contexto

Há três tipos de risco: lógica errada (regras), integração errada (SQL, triggers, HTTP) e qualidade de IA (modelo). Cada um pede um tipo de teste diferente, e a CI não deve depender de chave de API paga nem de comportamento não determinístico.

## Drivers de decisão

- CI rápida (alvo: abaixo de 5 minutos), determinística e gratuita.
- Cobrir as garantias declaradas (citação, recusa, aprovação, auditoria).
- Separar "o código está certo" de "o modelo é bom".

## Opções consideradas

**A. Pirâmide em três níveis (unitário, integração, avaliação), com a avaliação real fora da CI (escolhida)**
- Prós: cada nível mede uma coisa; a CI é estável.
- Contras: a avaliação com modelos reais não é automatizada a cada push (aceito pelo custo e pela variância).

**B. Tudo em CI, inclusive chamadas reais a LLM**
- Prós: pega regressão de prompt.
- Contras: custo, segredos em CI, flakiness.

**C. Só testes unitários**
- Prós: simples.
- Contras: não verifica triggers do banco nem a busca; garantias de auditoria ficariam sem teste.

**D. Gravação e replay de respostas do LLM (VCR)**
- Prós: testa o adaptador sem rede.
- Contras: fixtures grandes e frágeis. Usar só no adaptador OpenRouter, em pequena escala.

## Decisão

Opção A.

| Nível | O que cobre | Ferramentas | Roda onde |
|---|---|---|---|
| Unitário | Domínio e casos de uso com fakes: validação de citação (paráfrase, acentos, espaços), limiar de recusa, transições de estado, hash da auditoria, circuit breaker com relógio falso | `pytest` | Local e CI |
| Integração | Postgres real: migrations, retriever híbrido, trigger que bloqueia `UPDATE/DELETE`, verificação da cadeia, rotas HTTP ponta a ponta com `FakeLLM` | `pytest`, serviço Postgres+pgvector (service container na CI, `testcontainers` ou Compose localmente) | Local e CI |
| Contrato | `openapi.yaml` publicado igual ao gerado pela aplicação; marcadores de conteúdo fictício presentes em todos os procedimentos | `pytest` | CI |
| Avaliação determinística | Suíte de cenários com `FakeLLM` (testa o encanamento e as métricas) | `make eval-fake` | CI |
| Avaliação real | 2 modelos x com/sem RAG | `make eval` | Manual, relatório versionado |

CI no GitHub Actions: jobs de lint (`ruff`, `mypy` em modo moderado), testes (unitário + integração + contrato) e `eval-fake`. Cache de dependências com `uv` ou `pip`. Chave do OpenRouter não é exposta à CI.

Meta de cobertura: acompanhada, sem gate rígido. Regra prática: o domínio e a aplicação cobertos de forma quase integral; adaptadores cobertos pela integração.

## Consequências

- Regressão de qualidade do modelo ou do prompt só aparece quando alguém roda `make eval`. A mitigação é registrar a versão do prompt nos relatórios e rodar a avaliação antes de qualquer mudança de prompt ou modelo.
- Ter o `eval-fake` na CI garante que o código de avaliação não quebre sem que ninguém perceba.
- Testes de integração exigem Docker na CI; o job é mais lento que os demais (cerca de 1 a 2 minutos).
