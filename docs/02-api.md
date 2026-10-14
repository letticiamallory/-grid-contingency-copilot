# 02 - API

Contrato inicial. O `openapi.yaml` ao lado é a versão formal; a implementação deve gerar um OpenAPI equivalente (teste de contrato, ADR-010).

Convenções:

- JSON, UTF-8. IDs são UUIDs. Datas em ISO 8601 com fuso.
- Toda resposta de sugestão inclui `disclaimer` (ADR-007).
- Erros seguem o formato `{"error": {"code": "...", "message": "...", "details": {...}}}`.
- Sem autenticação; `reported_by` e `decided_by` são textos livres (limitação declarada).

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Verificação de saúde (API e banco) |
| POST | `/events` | Registra um evento |
| GET | `/events/{event_id}` | Consulta um evento |
| POST | `/events/{event_id}/suggestions` | Gera sugestão (ou recusa) |
| GET | `/suggestions/{suggestion_id}` | Consulta uma sugestão |
| POST | `/suggestions/{suggestion_id}/decision` | Aprova ou rejeita |
| GET | `/events/{event_id}/audit` | Trilha de auditoria do evento |

## Payloads

### POST /events

```json
{
  "type": "line_trip_by_protection",
  "element": "LT-FICT-230-04",
  "occurred_at": "2026-03-14T02:41:00-03:00",
  "attributes": {"protection": "distance", "zone": 1, "reclosing": "failed"},
  "reported_by": "operador.teste"
}
```

Resposta `201`: o evento com `id`.

### POST /events/{event_id}/suggestions

Sem corpo. A escolha do modelo por requisição não está implementada: o modelo é o configurado no servidor (ADR-005).

Resposta `201`, sugestão com passos:

```json
{
  "id": "5b0f...",
  "event_id": "9c1d...",
  "status": "pending_review",
  "refusal_reason": null,
  "model": "provider/model-a",
  "prompt_version": "v1",
  "steps": [
    {
      "position": 1,
      "instruction": "Confirmar o estado dos disjuntores nas duas extremidades da linha.",
      "citations": [
        {
          "procedure_code": "PO-FICT-001",
          "procedure_version": "1.0",
          "section": "4.1 Verificações iniciais",
          "quote": "confirmar a posição dos disjuntores em ambas as extremidades"
        }
      ]
    }
  ],
  "disclaimer": "Conteúdo fictício. Não usar em operação real."
}
```

Resposta `201` para recusa (a recusa é um resultado válido, não um erro):

```json
{
  "id": "7a22...",
  "event_id": "9c1d...",
  "status": "refused",
  "refusal_reason": "no_applicable_procedure",
  "steps": [],
  "disclaimer": "Conteúdo fictício. Não usar em operação real."
}
```

Valores de `refusal_reason`: `no_applicable_procedure`, `model_declined`, `no_valid_citation`.

Sugestões com `status = refused` não aceitam decisão.

### POST /suggestions/{suggestion_id}/decision

```json
{
  "outcome": "reject",
  "justification": "O passo 2 não se aplica a esta configuração de barramento.",
  "decided_by": "operador.teste"
}
```

`justification` é obrigatória quando `outcome = reject`. Resposta `200`: a sugestão com `status` `approved` ou `rejected`.

### GET /events/{event_id}/audit

```json
{
  "event_id": "9c1d...",
  "chain_valid": true,
  "entries": [
    {"seq": 101, "kind": "EVENT_RECEIVED", "at": "2026-03-14T05:41:03Z", "payload": {}, "hash": "ab12..."}
  ]
}
```

## Erros

| HTTP | `code` | Quando |
|---|---|---|
| 400 | `invalid_payload` | Campo ausente ou inválido (detalhes em `details`) |
| 404 | `event_not_found`, `suggestion_not_found` | ID inexistente |
| 409 | `suggestion_not_pending` | Decisão em sugestão recusada ou já decidida |
| 422 | `justification_required` | Rejeição sem justificativa |
| 503 | `llm_unavailable` | Todos os modelos falharam (timeout, breaker aberto) |
| 500 | `internal_error` | Falha não prevista; o corpo não vaza detalhes internos |

Observação: `invalid_payload` usa 400 e `justification_required` usa 422 por serem erros de regra de negócio sobre um payload bem formado. Se isso parecer inconsistente na implementação, unificar em 422.
