# Plano de testes, evidências e critérios de aceite

## Resultados observados

| Evidência | Situação | Fonte |
|---|---|---|
| 15 testes base e 8 adicionais | **23/23 passaram** no Windows, 17/11/2026 | Saída pytest fornecida pelo autor: `23 passed, 1 warning in 42.52s` |
| Saúde FastAPI | HTTP 200 + `{"status":"ok"}` | `curl.exe` no Windows e consulta interna Docker |
| UTF-8 | SQLite e API sem marcadores de mojibake em TCK-0005 | Diagnóstico `python -m app.workers.diagnose_utf8 TCK-0005` |
| Modelo de IA | TCK-0006 registrou `model_name=gpt-6-luna` e `provider_model=gpt-6-luna` | GET do chamado fornecido pelo autor |
| Triagem e sincronização | TCK-0006: `analysis_status=succeeded`, `sync_status=succeeded` | GET do chamado |
| Fluxo humano | `created → processing → awaiting_review → in_progress → resolved → closed` | Histórico SQLite via GET; capturas da interface |
| Auditoria da prioridade | `medium → medium`, ator `attendant`, justificativa preservada | `priority_reviews` retornado pelo GET |
| Linha Sheets | Autor confirmou **uma linha** para TCK-0006 | Conferência manual; não é teste de concorrência |
| Frontend React conectado | Indicador API conectada e detalhes TCK-0006 | Capturas enviadas pelo autor |
| Build `npm run build` | **Não comprovado** | Executar antes do GitHub |
| Instalação limpa | **Não comprovada** | Executar em ambiente separado |

## O que cobrem os oito testes da Etapa 8

1. Webhook repetido sem duplicar a chamada simulada à IA.
2. Chave de serviço ausente e tentativa de evento inconsistente.
3. Callback de sincronização repetido.
4. Falha e posterior recuperação de sincronização simulada.
5. Indisponibilidade HTTP simulada do n8n, com retry da Outbox.
6. Limite de tentativas e estado `dead_letter`.
7. Falha de análise e reenvio autorizado por atendente com novo `event_id`.
8. Proibição de encerramento indevido, restrição de papel simulado e exigência de nota de resolução.

**Limite:** a automação não interage com OpenAI, n8n ou Sheets reais. O teste humano ponta a ponta foi observado com um chamado sintético, mas não se executou um teste sistemático de falhas externas reais ou alta concorrência.

## Verificações finais seguras (somente leitura)

```powershell
# Na raiz do projeto existente
curl.exe http://127.0.0.1:8000/health
$ticket = Invoke-RestMethod 'http://127.0.0.1:8000/tickets/TCK-0006'
$ticket | Select-Object public_id,ticket_status,analysis_status,sync_status
$ticket.history | Select-Object previous_status,new_status,actor_type,reason
$ticket.priority_reviews | Select-Object previous_priority,new_priority,actor_type,reason
```

Não reutilize TCK-0006 para ensaios destrutivos: ele é uma evidência persistida do fluxo completo. Para um novo ensaio, crie um chamado **fictício**, de preferência com `AI_MODE=mock` e planilha separada. A execução real da OpenAI pode ter custos.

## Imagens sugeridas para `docs/evidence/`

Guarde somente capturas revisadas e sem tokens, emails, IDs de planilha privados ou conteúdo de usuários reais:

- `01-painel.png`: painel React e estado conectado.
- `02-analise.png`: análise fictícia, prioridade, recomendações e rastreabilidade.
- `03-revisao.png`: histórico de revisão humana justificada.
- `04-encerramento.png`: estado fechado e controles desabilitados.
- `05-testes.png`: saída `23 passed` sem caminho pessoal ou ambiente privado, após recorte.

Não são anexadas capturas automaticamente, porque devem ser revisadas/redigidas pelo autor antes da publicação.

## Próximas verificações

- Executar `npm run build` e conferir sua saída.
- Fazer instalação limpa isolada, com `AI_MODE=mock` e credenciais fictícias, sem migrar volumes existentes.
- Opcional: executar teste real de recuperação em cópia do ambiente, planilha dedicada e dados sintéticos.
