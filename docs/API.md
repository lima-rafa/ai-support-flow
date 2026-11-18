# API — contratos implementados

Base local: `http://127.0.0.1:8000`. Documentação interativa: `/docs`. Contratos conferidos em `backend/app/main.py` e `backend/app/schemas.py` do pacote v0.4 (backend v0.3).

| Método | Rota | Uso | Controle |
|---|---|---|---|
| GET | `/health` | Verificar saúde HTTP | Público local |
| POST | `/tickets` | Criar chamado; retorna 201 | Público local |
| GET | `/tickets` | Listar chamados | Público local |
| GET | `/tickets/{ticket_id}` | Obter detalhes, análises e histórico | Público local |
| PATCH | `/tickets/{ticket_id}/status` | `in_progress`, `resolved`, `closed` | `X-Demo-Role: attendant` |
| PATCH | `/tickets/{ticket_id}/priority` | Revisar prioridade justificada | `X-Demo-Role: attendant` |
| POST | `/tickets/{ticket_id}/retry-analysis` | Agendar retry de análise falha; retorna 202 | `X-Demo-Role: attendant` |
| POST | `/internal/tickets/{ticket_id}/analyze` | Processamento por `event_id` | `X-Service-Key` |
| POST | `/internal/tickets/{ticket_id}/sync-status` | Callback de sincronização por `event_id` | `X-Service-Key` |

> **Atenção:** cabeçalho `X-Demo-Role` não autentica ninguém; apenas simula o fluxo local. Rotas internas só devem ser chamadas pelo workflow com a chave configurada. Não inclua segredos em exemplos publicáveis.

## Payloads

**Criar ticket** (`POST /tickets`):

```json
{
  "title": "Falha de acesso ao email",
  "description": "Um usuario relata que nao consegue abrir o email corporativo ficticio.",
  "affected_service": "email",
  "reported_impact": "single_user",
  "impact_scope": "individual"
}
```

`title` exige 4–150 caracteres; `description`, 10–5000. `impact_scope`: `unknown`, `individual`, `partial`, `blocked`, `multiple` ou `widespread`. O `POST` cria um registro real no ambiente conectado: use dados sintéticos e evite repeti-lo por engano.

**Revisar prioridade** (`PATCH /tickets/{id}/priority`):

```json
{"priority":"medium","reason":"Impacto individual confirmado pelo atendente demonstrativo."}
```

Prioridades: `low`, `medium`, `high`, `critical`. `reason` exige 8–300 caracteres. A sugestão original da IA continua disponível para auditoria.

**Mudar estado** (`PATCH /tickets/{id}/status`):

```json
{"status":"in_progress","reason":"Atendente iniciou a análise do caso fictício."}
```

Ao resolver, o sistema exige `resolution_notes` segundo as regras de domínio, por exemplo:

```json
{"status":"resolved","resolution_notes":"Falha simulada corrigida e acesso testado em ambiente fictício."}
```

**Retry:** `POST /tickets/{id}/retry-analysis` não recebe payload obrigatório. Retorna 202 apenas quando a nova tentativa é registrada, não quando concluída.

**Chamadas internas:** analisar recebe `{"event_id":"<UUID do evento>"}`. Sincronizar recebe `{"event_id":"<UUID>","status":"succeeded","failure_stage":"none"}` ou `status="failed"` com estágio/erro apropriados. Não inclua chave real no repositório.

## Saída do chamado

`GET /tickets/{id}` retorna `public_id`, `ticket_status`, `analysis_status`, `sync_status`, `analysis`, `history` e `priority_reviews`, entre outros campos. Em `analysis`: `category`, `suggested_priority`, `effective_priority`, `summary`, `recommendations`, `review_reason`, `model_name`, `provider_model`, `prompt_version`, `error_code`.

`model_name` é o modelo solicitado; `provider_model` é o identificador retornado pelo provedor quando disponível. `provider_model=null` em análises antigas ou sem essa informação.

## Erros e proteção de estado

Os erros de domínio são retornados como `{"error_code":"..."}`. Exemplos de códigos: `INVALID_STATUS_TRANSITION`, `RETRY_REQUIRES_FAILED_ANALYSIS`, `TICKET_ALREADY_RESOLVED`. Papel ausente retorna HTTP 403; serviço interno não autorizado, HTTP 401. Em alguns casos, a validação Pydantic retorna HTTP 422.

Documentação interativa refletirá o ambiente em execução e deve prevalecer para diferenças entre revisões do backend.
