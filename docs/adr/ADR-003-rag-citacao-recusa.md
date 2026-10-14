# ADR-003: RAG com citação obrigatória e recusa explícita

- Status: aceito
- Data: a preencher

## Contexto

Sugestões operativas só têm valor se forem rastreáveis ao procedimento. Um LLM sem fundamentação pode inventar passos plausíveis. O requisito central do projeto é: nenhum passo sem fonte verificável, e recusa quando não houver fonte.

## Drivers de decisão

- Verificabilidade por código, não pela confiança no modelo.
- Custo de um falso positivo (passo inventado) maior que o de uma recusa indevida.
- Simplicidade: poucos componentes.
- Mensurabilidade na avaliação.

## Opções consideradas

**A. LLM puro, sem recuperação**
- Prós: simplicidade.
- Contras: nenhuma rastreabilidade; alucinação sem controle. Fica na avaliação apenas como baseline "sem RAG".

**B. RAG com pedido de citação no prompt, sem verificação**
- Prós: simples.
- Contras: o modelo pode citar fonte que não diz aquilo, ou inventar a citação. Citação não verificada dá falsa confiança, o que é pior que não ter citação.

**C. RAG com citação estruturada e verificação programática (escolhida)**
- O modelo devolve JSON: lista de passos, cada um com `chunk_id` e `quote` (trecho literal do chunk).
- O código verifica que `quote` existe no texto do chunk (após normalização de espaços e caixa) e que o `chunk_id` estava entre os recuperados. Passo que falha é descartado.
- Prós: garante que a citação existe; mede-se a taxa de descarte.
- Contras: verificação literal não garante que o passo decorre do trecho (fidelidade semântica); rejeita paráfrases legítimas.

**D. C + verificação semântica por um segundo LLM (juiz)**
- Prós: ataca o ponto fraco de C.
- Contras: mais custo, latência e um segundo ponto de erro. Fica no escopo da avaliação offline, não no caminho da requisição.

## Decisão

Opção C no fluxo principal. A opção D entra apenas na avaliação, como medida de fidelidade, com amostra checada manualmente para calibrar o juiz.

A recusa ocorre em três situações, cada uma com código de motivo:
1. `no_applicable_procedure`: o melhor score da recuperação está abaixo do limiar. O limiar é calibrado na avaliação, não escolhido a priori.
2. `model_declined`: o modelo recebeu a opção explícita de responder `{"refusal": "..."}` e a usou.
3. `no_valid_citation`: todos os passos foram descartados pela verificação.

## Consequências

- A garantia é "toda citação existe e foi recuperada", não "toda sugestão está correta". O README e `06-riscos-e-limitacoes.md` dizem isso com essas palavras.
- A verificação é um módulo puro do domínio (`citation.py`), fácil de testar com casos de paráfrase, espaços e acentos.
- O limiar de recusa troca recusa indevida por alucinação; a curva dessa troca é um resultado da avaliação.
- Procedimentos revisados mudam o texto: a citação guarda `procedure.version` e `content_hash` para a auditoria apontar o texto exato.
