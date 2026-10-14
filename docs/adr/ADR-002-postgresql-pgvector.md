# ADR-002: PostgreSQL com pgvector para armazenamento e busca

- Status: aceito (com ressalva sobre o valor da busca vetorial, ver Consequências)
- Data: a preencher

## Contexto

O sistema precisa de dois tipos de armazenamento: dados relacionais (eventos, sugestões, decisões, auditoria) e busca sobre os procedimentos. A base de conhecimento é minúscula: 10 a 15 procedimentos, algo como 100 a 300 chunks.

## Drivers de decisão

- Um banco já é necessário para a auditoria (transacional, com garantias).
- Reduzir contêineres e operação.
- A busca precisa ser boa o bastante para a avaliação ser significativa.
- Honestidade de escopo: não adicionar infraestrutura que a escala não pede.

## Opções consideradas

**A. PostgreSQL + pgvector + full-text (busca híbrida)**
- Prós: um único serviço; transação cobre dados e índice; `tsvector` dá busca lexical; pgvector dá similaridade; SQL permite filtrar por metadados.
- Contras: recursos de busca menos ricos que os de um motor dedicado; ajustar a fusão híbrida (RRF) dá trabalho.

**B. PostgreSQL + busca lexical apenas (`tsvector`/BM25-like)**
- Prós: nenhuma dependência de embeddings, sem custo de API de embeddings, determinístico, rápido de implementar.
- Contras: vocabulário de operação pode variar entre o evento e o procedimento ("desligamento", "abertura", "trip"), e isso derruba a recuperação; sem similaridade semântica.

**C. Banco vetorial dedicado (Qdrant, Weaviate, Chroma)**
- Prós: recursos de busca vetorial mais completos; bom a partir de milhões de vetores.
- Contras: um serviço a mais para operar; sincronização com o Postgres; nenhum ganho mensurável com 300 vetores.

**D. Índice em memória (numpy/FAISS), sem banco para busca**
- Prós: zero infraestrutura; para 300 vetores, é instantâneo.
- Contras: perde persistência e filtragem junto dos dados; é menos "produto" e menos defensável numa conversa técnica sobre rastreabilidade.

## Decisão

PostgreSQL com pgvector e `tsvector`, busca híbrida com fusão por rank (RRF), `k = 6`. A opção B entra na avaliação como baseline: a pergunta "a busca vetorial se paga?" é respondida com número, não por suposição.

Não vou criar índice ANN (HNSW/IVFFlat). Com poucas centenas de linhas, varredura exata é mais rápida e mais precisa. Registrar isso no README evita a impressão de que o índice foi esquecido.

## Consequências

- Se a avaliação mostrar que o lexical sozinho empata com o híbrido, o resultado é publicado e pgvector fica como opção, não como mérito. É um resultado aceitável e até interessante.
- A dimensão do vetor fica acoplada ao modelo de embedding. Trocar o modelo exige reindexar (o `content_hash` do procedimento viabiliza reindexação seletiva).
- Embeddings via OpenRouter ou outro provedor adicionam uma dependência externa na ingestão; os vetores são calculados uma vez e persistidos. Se o OpenRouter não oferecer um modelo de embedding adequado no momento, usar um modelo local pequeno (sentence-transformers) é a alternativa, ao custo de uma imagem Docker maior. Ponto a confirmar na implementação.
