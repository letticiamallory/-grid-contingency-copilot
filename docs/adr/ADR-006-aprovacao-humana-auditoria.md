# ADR-006: Aprovação humana obrigatória e trilha de auditoria imutável

- Status: aceito
- Data: a preencher

## Contexto

Em operação elétrica, a decisão é do operador. O sistema só sugere. É preciso reconstruir depois o que foi sugerido, com base em quê, e quem decidiu o quê.

## Drivers de decisão

- Impossibilidade, por construção, de uma sugestão virar "aprovada" sem decisão humana.
- Reconstruir o histórico de um evento.
- Detectar alteração posterior dos registros.
- Custo de implementação compatível com 20 h.

## Opções consideradas

### Aprovação humana

**A. Estado `approved` só alcançável via caso de uso `RecordDecision`, com `CHECK` no banco (escolhida)**
- Prós: regra no domínio e no banco; testável.
- Contras: o operador é identificado só por texto, sem autenticação (limitação declarada).

**B. Aprovação automática por limiar de confiança**
- Prós: mais fluidez.
- Contras: contradiz o requisito; descartada.

### Auditoria

**1. Tabela append-only no Postgres com encadeamento por hash (escolhida)**
- Cada linha guarda `prev_hash` e `hash = SHA-256(prev_hash || payload canônico)`. Um `TRIGGER` bloqueia `UPDATE` e `DELETE`, e o papel de banco da aplicação não tem esses privilégios na tabela.
- Prós: simples; verificável por um comando; sem serviço extra.
- Contras: não é imutável de verdade contra quem tem superusuário do banco; o hash detecta alteração, não a impede.

**2. Event sourcing completo**
- Prós: histórico é a fonte da verdade.
- Contras: complexidade desproporcional.

**3. Ledger externo (QLDB-like, blockchain, WORM storage)**
- Prós: imutabilidade mais forte.
- Contras: infraestrutura e custo fora de proporção; blockchain não acrescentaria garantia relevante aqui.

**4. Apenas logs de aplicação**
- Prós: nenhum esforço.
- Contras: não é consultável nem verificável; não atende RF-08.

## Decisão

Aprovação via A. Auditoria via opção 1.

Eventos auditados: `EVENT_RECEIVED`, `RETRIEVAL_DONE`, `LLM_CALLED`, `CITATIONS_VALIDATED`, `SUGGESTION_CREATED`, `REFUSED`, `DECISION_RECORDED`. O payload de cada um inclui os identificadores e versões necessários (modelo, versão do prompt, `procedure.version`, `content_hash`).

Um comando `make audit-verify` percorre a cadeia por evento e acusa a primeira linha cujo hash não confere. A concorrência é tratada com um lock consultivo por `event_id` ao acrescentar, para a ordem da cadeia ser determinística.

## Consequências

- O termo "imutável" no título é uma meta de projeto; o README descreve a garantia real: acréscimo apenas via aplicação, adulteração detectável, sem proteção contra um administrador de banco mal-intencionado. Para isso valeria ancorar o hash final em um sistema externo, deixado como próximo passo.
- Dados pessoais não entram na auditoria (só o identificador textual do operador), o que evita o conflito entre imutabilidade e direito de exclusão.
- A decisão de rejeitar exige justificativa, e esse texto também é auditado, o que alimenta a análise de erros na avaliação.
