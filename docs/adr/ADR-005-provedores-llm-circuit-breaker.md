# ADR-005: Abstração de provedores de LLM com OpenRouter e circuit breaker com fallback

- Status: aceito
- Data: a preencher

## Contexto

A avaliação precisa comparar dois modelos, e a API precisa continuar útil (ou falhar de forma clara) quando um modelo estiver lento ou fora do ar. O OpenRouter dá uma API única para vários modelos.

## Drivers de decisão

- Trocar de modelo por configuração, sem mudar código.
- Comparar modelos na avaliação com o mesmo código de chamada.
- Falhar de forma previsível: nunca devolver sugestão sem citação por causa de um fallback mal feito.
- Não construir infraestrutura de resiliência maior que o sistema.

## Opções consideradas

**A. Porta `LLMPort` + adaptador OpenRouter + circuit breaker e fallback próprios**
- Prós: o domínio não conhece o provedor; testável com `FakeLLM`; o comportamento de falha é código visível e testável.
- Contras: é código a manter; o breaker é uma peça a mais.

**B. SDK direto do provedor (ex.: Anthropic ou OpenAI) sem abstração**
- Prós: menos código; acesso a recursos específicos.
- Contras: acopla ao provedor; comparar modelos de provedores diferentes exige mais de uma integração.

**C. Biblioteca de roteamento (LiteLLM)**
- Prós: fallback, retry e muitos provedores prontos.
- Contras: dependência grande para um caso simples; esconde o comportamento de falha que se quer demonstrar. Aceitável se o tempo apertar.

**D. Sem breaker, só timeout e retry**
- Prós: bem mais simples.
- Contras: com um provedor degradado, cada requisição espera o timeout inteiro.

## Decisão

Opção A. Detalhes:

- `LLMPort.complete(prompt, schema, model) -> LLMResult`, com saída estruturada (JSON validado por schema).
- Adaptador OpenRouter via HTTP (cliente `httpx`), timeout de 20 s, no máximo 1 retry com backoff para erros 5xx e timeout. Não há retry em 4xx.
- Circuit breaker mínimo por modelo: abre após 3 falhas consecutivas e fica aberto por 30 s, depois testa uma chamada (meia-abertura). Implementação própria de cerca de 40 linhas, com relógio injetável para teste.
- Fallback: modelo primário falhou ou breaker aberto, usa o secundário configurado. O modelo efetivamente usado vai para `SUGGESTION.model` e para a auditoria. Se ambos falharem, a API responde 503 com código `llm_unavailable`. Não há degradação para "sugestão sem LLM".

Assumo que o breaker é, para este volume, mais demonstração de critério que necessidade operacional. Ele é pequeno, e o ganho real está em mostrar como o sistema se comporta sob falha. Se o orçamento de horas apertar, é o primeiro item a cortar, mantendo timeout e retry.

## Consequências

- Resultados de modelos diferentes podem divergir por detalhes de formato de saída estruturada; o adaptador normaliza e a avaliação registra erros de parsing por modelo.
- O fallback altera o comportamento: a mesma requisição pode ter respostas diferentes dependendo da disponibilidade. Por isso o modelo usado é auditado.
- Na avaliação, o fallback é desligado, para não misturar modelos numa mesma coluna de resultado.
- Dependência de um intermediário (OpenRouter) soma uma camada de latência e um ponto de falha; é aceito para o escopo.

## Atualização da implementação (14/10/2026)

Implementado em `adapters/outbound/llm/`: `OpenRouterLLM` (timeout 20 s, 1 retry com backoff para timeout, erro de rede, 429 e 5xx; sem retry em outros 4xx) e `FallbackLLM` com `CircuitBreaker` (3 falhas, 30 s, meia-abertura com uma tentativa), relógio injetável. A porta ficou `complete(system, user) -> LLMResponse(text, model)`; a validação do JSON é feita pelo caso de uso, não por schema no provedor. Sem chave ou sem `LLM_MODEL`, a API responde 503. Verificado só com `httpx.MockTransport`; não foi exercitado contra a API real.
