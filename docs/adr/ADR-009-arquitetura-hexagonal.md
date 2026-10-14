# ADR-009: Arquitetura hexagonal e testabilidade

- Status: aceito (em versão enxuta)
- Data: a preencher

## Contexto

O sistema depende de três coisas instáveis ou caras: LLM, banco e (para ingestão) embeddings. O núcleo, que é a regra de recusa, a verificação de citação e o fluxo de aprovação, deve ser testável sem nenhuma delas.

## Drivers de decisão

- Testes rápidos e determinísticos do que importa.
- Trocar o modelo, o provedor ou o retriever sem tocar nas regras.
- Não gastar o orçamento de 20 h em cerimônia.

## Opções consideradas

**A. Hexagonal completa: domínio, aplicação com portas, adaptadores, composição no `main`**
- Prós: separa regra de I/O; `FakeLLM` e repositórios em memória viram naturais; fácil explicar.
- Contras: mais arquivos e indireção para um sistema pequeno; risco de portas inúteis.

**B. Camadas simples (routers, services, repositórios) sem portas formais**
- Prós: menos código.
- Contras: serviços acabam importando o cliente do LLM e o ORM; testar exige mocks de bibliotecas.

**C. Script/notebook**
- Prós: mínimo.
- Contras: não demonstra engenharia; sem testes sérios.

## Decisão

Opção A, enxuta. Portas só onde há uma fronteira real de I/O ou variação real: `LLMPort`, `EmbedderPort`, `RetrieverPort`, repositórios de evento/sugestão/decisão, `AuditLog` e `Clock`. Não haverá porta para o que não varia (ex.: serialização, logging). Python `Protocol` em vez de classes abstratas; sem contêiner de injeção de dependência, apenas funções de composição em `main.py`.

O domínio usa dataclasses imutáveis. Os schemas Pydantic ficam na borda HTTP.

## Consequências

- Os testes unitários cobrem as regras de recusa, validação de citação, transições de estado e geração do hash da auditoria, sem rede e sem banco.
- Os testes de integração cobrem os adaptadores Postgres (retriever, auditoria, triggers) contra um banco real.
- Um `FakeLLM` programável (respostas por cenário) permite testar o caso de uso em todos os caminhos, inclusive saídas malformadas.
- Custo aceito: cerca de 10% mais de código de estrutura. Se a estrutura estiver tomando mais tempo que a regra, simplificar as portas dos repositórios (juntar em uma única `Repository`).
- Uma ressalva: para um sistema deste tamanho a arquitetura não é necessária. Ela se justifica aqui porque o objetivo do projeto inclui demonstrá-la, e o custo é baixo.
