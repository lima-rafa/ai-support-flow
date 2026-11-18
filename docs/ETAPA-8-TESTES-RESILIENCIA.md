# ASF — Etapa 8: testes de integração lógica, falhas e idempotência

**Pacote de testes não destrutivo para o AI Support Flow.** Aplicável à árvore operacional que contém o backend v0.3 integrado e o frontend v0.4. Este pacote **somente adiciona** `backend/tests/test_resilience_stage8.py` e este documento. Não substitui o `.env`, o SQLite, a configuração do Docker, o workflow n8n ou o React.

## Resultado obtido no ambiente de desenvolvimento

Com a aplicação extraída do pacote `AI-SUPPORT-FLOW-ETAPA-7-REACT-v0.4.zip`, executou-se na pasta `backend`:

```text
python -m pytest -q
.......................
23 passed in 1.08s
```

São 15 testes anteriores + 8 novos testes da Etapa 8. O tempo varia conforme a máquina. Os testes isolam todas as integrações com simulações HTTP (`httpx.MockTransport`), SQLite temporário (`tmp_path`) e adaptador de IA de teste. **Não usam a API OpenAI real e não alteram os dados do usuário.**

## Matriz de casos automatizados

| ID | Cenário | Assertivas principais |
|---|---|---|
| E8-01 | Webhook repetido 3 vezes | Uma única análise e uma única chamada ao adaptador de IA |
| E8-02 | Serviço interno sem chave ou com evento de outro ID | Respostas 401/409 sem execução da IA |
| E8-03 | Callback do Sheets repetido | Um único registro de sincronização; tentativas não incrementam após sucesso |
| E8-04 | Sheets falha e depois se recupera | Análise preservada, estado `retry` seguido de `completed` |
| E8-05 | n8n temporariamente indisponível | Dispatcher agenda retry; após HTTP 200 permanece `sent` até o callback final |
| E8-06 | Quatro falhas de entrega | Transição da Outbox para `dead_letter`; não há reentrega automática posterior |
| E8-07 | IA falha e atendente solicita nova tentativa | Resposta genérica sem segredo interno, novo `event_id`, histórico de ambas as análises |
| E8-08 | Encerramento controlado por atendente | Sem papel demonstrativo: 403; transição inválida: 409; resolução sem nota: 422; fechamento final preservado |

## Como integrar no Windows PowerShell

Na pasta operacional `AI-SUPPORT-FLOW-ETAPA-3-v0.2\ai-support-flow`, após extrair o ZIP desta Etapa 8 na pasta Downloads:

```powershell
$zip = "$env:USERPROFILE\Downloads\AI-SUPPORT-FLOW-ETAPA-8-TESTES-v0.5.zip"
Expand-Archive -Path $zip -DestinationPath ".\_etapa8" -Force
Copy-Item ".\_etapa8\backend\tests\test_resilience_stage8.py" ".\backend\tests\test_resilience_stage8.py" -Force
Copy-Item ".\_etapa8\docs\ETAPA-8-TESTES-RESILIENCIA.md" ".\docs\ETAPA-8-TESTES-RESILIENCIA.md" -Force
```

### Execução recomendada, sem modificar serviços Docker

Se há Python instalado no Windows:

```powershell
cd .\backend
py -m venv .venv-stage8
.\.venv-stage8\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv-stage8\Scripts\python.exe -m pytest -q
cd ..
```

O comando executa os testes com bancos em diretórios temporários do pytest, sem conexão com o ambiente Docker em execução. Se não houver Python instalado no Windows, instale Python 3.12+ ou utilize um contêiner separado de testes com as dependências de `requirements-dev.txt`. A imagem `backend` de produção não instala pytest por padrão.

## O que os testes NÃO comprovam

- A disponibilidade real da OpenAI, do n8n e da API do Google Sheets no momento do teste.
- Que o workflow publicado no n8n se comportará exatamente como a simulação HTTP.
- Que a planilha externa não terá linhas duplicadas após falhas de rede ou callback perdido.
- Que múltiplos dispatchers ou múltiplas instâncias FastAPI são seguros em produção. O projeto opera em modo de demonstração de instância única.
- Que o `X-Demo-Role` é autorização segura: ele é apenas uma simulação local e é facilmente falsificável.
- Recuperação automática de eventos em `dead_letter`: o estado sinaliza necessidade de intervenção, não uma recuperação autônoma.

## Inspeções manuais recomendadas (sem criar chamados)

1. Conferir que `TCK-0006` permanece `closed` após atualização de página e reinício apenas do navegador.
2. Conferir que uma consulta GET ao `TCK-0006` mostra o histórico completo de estados e a revisão de prioridade.
3. Confirmar se a planilha `Chamados` tem uma única linha por `ticket_id`; isso é uma inspeção, não um teste de falha forçada.
4. Analisar as execuções históricas do n8n, sem reexecutar o workflow ou acionar webhooks manuais.

Comandos PowerShell somente leitura:

```powershell
$ticket = Invoke-RestMethod 'http://127.0.0.1:8000/tickets/TCK-0006'
$ticket | Select-Object public_id,ticket_status,analysis_status,sync_status
$ticket.history | Select-Object previous_status,new_status,actor_type,reason,created_at
$ticket.priority_reviews | Select-Object previous_priority,new_priority,actor_type,reason,created_at
```

## Critério de aceite

- `23 passed` em ambiente isolado com o backend atualizado.
- TCK-0006 permanece encerrado e seu histórico permanece consultável.
- A inspeção manual da planilha e do n8n não mostra inconsistências relevantes.
- Falhas reais não são provocadas diretamente no ambiente operacional: caso se deseje um ensaio de ponta a ponta com indisponibilidade do Sheets, deve-se clonar todo o ambiente, usar uma planilha separada e chaves de teste.
