# ASF — Checkpoint de implementação 002

**Data:** 2026-11-13
**Baseline:** ASF-SPEC-001@1.0 e ASF-ARCH-001@1.0 (sem mudanças normativas).
**Implementação:** starter v0.2, continuação da Etapa 3.

## Alterações

- Endpoint `PATCH /tickets/{ticket_id}/priority`: correção/confirmacão humana com justificativa, auditoria em `priority_review_history`, bloqueio durante análise e após encerramento, confirmação crítica restrita a `impact_scope=widespread`.
- Endpoint `POST /tickets/{ticket_id}/retry-analysis`: cria novo evento atômico na Outbox quando análise falhou; evita duplicação de solicitações e mantém event IDs anteriores.
- Contagem de tentativas incrementada em `analysis_results.attempt_number`.
- Callback de sincronização de eventos anteriores rejeitado após análise mais recente.
- Análise iniciada não reverte o estado `in_progress` de atendimento assumido pelo atendente.
- Exposição do histórico de revisão de prioridade em `GET /tickets/{id}`.

## Evidências

`pytest -q` no diretório `backend/`: **13 testes aprovados**, incluindo os 10 originais. Cenários adicionais: revisão auditável, retry após falha, histórico de tentativas, callback antigo rejeitado e proteção durante análise. Os testes utilizam adaptadores simulados, sem provar integração real com n8n/OpenAI/Sheets.

## Limitações e pendências

- Docker/Compose e n8n não foram executados nesta sessão; workflow não validado ao vivo.
- Google Sheets e OpenAI real ainda exigem credenciais e testes integrados.
- O header `X-Demo-Role` é **somente para localhost**.
- Não está implementada autenticação de usuários de produção.
- Retry da Outbox é básico; operacionalização de dead-letter e testes de falha distribuída permanecem pendentes.
- React não implementado.

**Status:** Etapa 3 — backend ampliado e 13 testes verdes; validação integrada da Etapa 4 continua pendente.
