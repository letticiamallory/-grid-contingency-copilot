# ADR-001: FastAPI como framework da API

- Status: aceito
- Data: a preencher

## Contexto

O sistema expõe poucos endpoints (eventos, sugestões, decisões, auditoria) e precisa de documentação interativa, já que não haverá front-end. O LLM e o banco são I/O externo, então a latência é dominada por chamadas de rede.

## Drivers de decisão

- Swagger/OpenAPI gerado automaticamente, para servir de interface.
- Validação de payloads tipada.
- Suporte a async para as chamadas ao LLM.
- Pouco código de infraestrutura, dado o orçamento de 20 h.
- Facilidade de teste.

## Opções consideradas

**A. FastAPI**
- Prós: OpenAPI e Swagger gratuitos; Pydantic para validação; async nativo; `TestClient` simples; ecossistema Python do LLM.
- Contras: injeção de dependência é mais informal; é fácil deixar lógica de negócio vazar para as rotas.

**B. Flask**
- Prós: simples e conhecido.
- Contras: OpenAPI e validação exigem extensões; async é menos natural. Mais peças para obter o mesmo resultado.

**C. Django + DRF**
- Prós: ORM, admin e auth prontos.
- Contras: pesado para 4 endpoints; o ORM e o admin não ajudam numa arquitetura hexagonal com Postgres controlado por SQL. Sobra framework.

**D. NestJS (TypeScript)**
- Prós: domínio que a autora já conhece bem; DI forte.
- Contras: o ecossistema de RAG e avaliação é mais maduro em Python, e o objetivo do projeto é mostrar essa stack. Seria uma escolha por conforto, não por adequação.

## Decisão

FastAPI. Pesa a favor o Swagger como interface única do projeto. Django e NestJS são opções razoáveis, mas não trazem ganho para este escopo.

## Consequências

- As rotas ficam finas: convertem payload em chamada de caso de uso e mapeiam erros de domínio para HTTP.
- Os schemas Pydantic ficam na camada de adaptador HTTP. O domínio usa dataclasses próprias, para não acoplar o núcleo ao framework.
- O `openapi.yaml` publicado em `docs/` é conferido contra o gerado pela aplicação em um teste.
