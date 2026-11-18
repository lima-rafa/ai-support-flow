---
document_id: ASF-SPEC-001
project: AI Support Flow
version: 1.0
status: approved
date: 2026-11-08
scope: MVP de portfolio para iFood AI Engineer
---

# AI Support Flow — Etapa 1: Especificação funcional (v0.1)

> **Estado:** APROVADO pelo usuário em 2026-11-08. Este documento é a baseline funcional do MVP.
> **Histórico:** consolidação da proposta v0.1 sem alteração de escopo; a v0.1 permanece preservada.

## 1. Visão e objetivo

Criar uma aplicação web de suporte de TI que receba relatos de problemas, persista chamados, use IA generativa para triagem assistida e empregue **n8n como orquestrador central** para acionar serviços, tratar rotas de sucesso/falha e registrar resultados em um sistema externo.

É um projeto original, com dados sintéticos, destinado ao portfólio. Não reproduz código, prompts, documentos ou regras confidenciais da Arrowplan ou Stellantis.

### Objetivo mensurável do MVP
Demonstrar, em execução local reproduzível, o percurso completo de um chamado — criação, processamento via n8n, classificação por IA, triagem/revisão, acompanhamento e encerramento humano — e evidenciar testes de sucesso e falha.

## 2. Usuários e atores

- **Solicitante:** abre chamado e acompanha situação.
- **Atendente:** consulta chamados, revisa classificações, altera status e encerra após resolução.
- **Serviço n8n:** orquestra a automação mediante evento autenticado.
- **OpenAI API:** provê análise generativa acessada pelo backend.
- **Google Sheets:** destino externo de registro demonstrativo, não a fonte de verdade.

**Autenticação simplificada MVP:** perfis de solicitante e atendente podem ser simulados em ambiente local, sem implantação de autenticação corporativa. Endpoints internos entre serviços exigem credencial de serviço; não expor operações administrativas anonimamente em ambiente público.

## 3. Escopo MVP

### Incluído
1. Formulário com título, descrição, serviço afetado e impacto percebido.
2. Criação de chamado com ID único e data/hora.
3. Armazenamento em banco SQLite pelo backend FastAPI.
4. Disparo autenticado de webhook para n8n depois da persistência.
5. n8n chama endpoint interno de análise do FastAPI, que invoca OpenAI.
6. Resposta estruturada: categoria, prioridade sugerida, resumo, recomendações e justificativa concisa.
7. Validação de schema e aplicação de regras determinísticas de prioridade/revisão no backend.
8. n8n registra resultado em Google Sheets e informa status da integração ao backend.
9. Painel React com lista, detalhe, status e revisão do atendente.
10. Conclusão e encerramento manual com descrição da solução.
11. Tratamento de falhas, registro de tentativas e testes automatizados.
12. Docker Compose e documentação de execução local, com workflow n8n exportável e sem credenciais.

### Fora do escopo MVP
Autenticação corporativa, integrações reais com Jira/ServiceNow, alertas multicanal, SLA de produção, RAG, agentes autônomos, hospedagem pública obrigatória e resolução/encerramento automáticos.

## 4. Fluxo ponta a ponta (F-01)

1. Solicitante envia o formulário no React.
2. FastAPI valida e grava `TCK-NNNN` com status `created`.
3. Backend solicita execução do webhook n8n com `ticket_id` e identificador único do evento (sem enviar dados pessoais desnecessários).
4. n8n recebe evento e faz HTTP Request autenticado ao endpoint `POST /internal/tickets/{id}/analyze`.
5. FastAPI carrega chamado, invoca OpenAI, valida saída estruturada, calcula prioridade efetiva e persiste análise.
6. n8n recebe resultado e segue caminho de sucesso ou erro.
7. Em sucesso: n8n registra linha/atualização na planilha Google Sheets e notifica o backend de sua sincronização.
8. Chamado recebe `awaiting_review` quando houver dúvida/impacto crítico, ou `triaged` caso contrário.
9. Atendente revisa e encaminha para `in_progress`.
10. Após resolução, atendente registra solução e muda para `resolved`; após validação final, encerra como `closed`.
11. Usuário acompanha evolução no painel.

**Se a IA falhar:** o chamado permanece salvo, recebe estado operacional de análise com falha e é encaminhado para revisão manual; o n8n registra o erro e impede perda silenciosa.

## 5. Requisitos funcionais

| ID | Requisito | Critério sucinto |
|---|---|---|
| RF-001 | Abrir chamado | título e descrição obrigatórios, ID gerado pelo servidor |
| RF-002 | Listar e consultar chamados | exibir status, data e histórico essencial |
| RF-003 | Persistir chamado | registro criado antes de acionar n8n |
| RF-004 | Disparar workflow n8n | evento com `ticket_id` e `event_id` únicos |
| RF-005 | Analisar relato via OpenAI | chamada realizada exclusivamente pelo backend |
| RF-006 | Validar saída da IA | resposta com tipos e categorias permitidos |
| RF-007 | Aplicar triagem determinística | regras podem sobrepor prioridade sugerida |
| RF-008 | Encaminhar à revisão humana | casos incertos/críticos ou falhas são revisáveis |
| RF-009 | Sincronizar registro externo com n8n | gravar/atualizar planilha sem duplicar registro |
| RF-010 | Gerenciar estados | impedir transições inválidas e registrar histórico |
| RF-011 | Encerrar chamado | exige ação do atendente e resolução documentada |
| RF-012 | Registrar erros e tentativas | permitir diagnosticar falhas sem expor secrets |

## 6. Regras de negócio

| ID | Regra |
|---|---|
| RN-001 | Um chamado não pode ser perdido por falha do n8n, OpenAI ou Google Sheets. |
| RN-002 | O backend é a fonte de verdade para chamados, status e prioridade efetiva; a planilha é projeção. |
| RN-003 | O modelo sugere prioridade; **o backend valida/limita o resultado** conforme impacto declarado e critérios conhecidos. |
| RN-004 | Prioridade crítica, relato ambíguo, resposta inválida ou falha de análise exigem revisão humana. |
| RN-005 | Nenhum chamado pode ser encerrado automaticamente pela IA ou pelo n8n. |
| RN-006 | Repetição do mesmo evento do n8n não deve duplicar análise ou linhas de planilha (`event_id`/`ticket_id` e operação idempotente). |
| RN-007 | A saída da IA não autoriza diretamente execução de comandos ou alteração de configurações de equipamentos. |
| RN-008 | Falhas externas são registradas e permitem nova tentativa controlada, sem duplicar efeitos persistentes. |

### Categorias iniciais
`network`, `hardware`, `software`, `access`, `email`, `other`.

### Prioridade
`low`, `medium`, `high`, `critical`. Critérios determinísticos propostos:
- `critical`: indisponibilidade ampla de serviço essencial informada e confirmada pelo atendente; exige revisão.
- `high`: múltiplos usuários afetados ou operação de trabalho bloqueada; exige revisão quando as informações não forem suficientes.
- `medium`: impacto parcial com alternativa operacional.
- `low`: orientação/dúvida ou problema sem bloqueio significativo.

A análise automática pode **sugerir**, mas não afirmar como fato um incidente amplo sem evidências do relato. Atendente pode retificar prioridade, registrando motivo.

## 7. Estados

Fluxo típico:
`created` → `processing` → (`triaged` | `awaiting_review`) → `in_progress` → `resolved` → `closed`.

Falha técnica de análise: `processing` → `awaiting_review` com `analysis_status=failed` (sem apagar o chamado). A conclusão manual pode prosseguir mesmo sem IA. Estado `closed` é terminal no MVP. Transições administrativas serão validadas no backend.

Separar `ticket_status` (estado do atendimento) de `analysis_status` (`pending`, `running`, `succeeded`, `failed`) e `sync_status` (`pending`, `succeeded`, `failed`).

## 8. Contrato da IA (proposta)

Entrada para o backend: ID do chamado; os dados são buscados do banco e minimizados antes do envio ao provedor.

Saída estruturada esperada, ilustrativa:

```json
{
  "category": "network",
  "suggested_priority": "high",
  "summary": "Usuários não conseguem acessar a internet no escritório.",
  "recommendations": [
    "Verificar se o problema afeta outras estações.",
    "Consultar o estado do gateway e dos equipamentos de rede."
  ],
  "review_reason": "Possível impacto coletivo informado no relato."
}
```

`effective_priority` e `requires_human_review` serão calculados/confirmados pelo backend, com regras testáveis. Não armazenar raciocínio privado do modelo. Mensagens do usuário são dados não confiáveis, nunca instruções de sistema.

## 9. Interfaces e endpoints propostos

- `POST /tickets` — criação.
- `GET /tickets` — listagem.
- `GET /tickets/{ticket_id}` — detalhe.
- `PATCH /tickets/{ticket_id}/status` — alteração controlada por atendente.
- `POST /internal/tickets/{ticket_id}/analyze` — análise iniciada pelo n8n com autenticação de serviço.
- `POST /internal/tickets/{ticket_id}/sync-status` — atualização de status de sincronização por n8n.

O backend aciona o webhook de entrada do n8n; detalhes de entrega confiável (tentativas/registro do evento) serão definidos na etapa de backend.

## 10. Não funcionais e segurança

- **RNF-001:** projeto inicia localmente com instruções reproduzíveis e configurações de ambiente exemplificadas.
- **RNF-002:** credenciais OpenAI/n8n/Google nunca aparecem no frontend, logs públicos ou repositório.
- **RNF-003:** webhooks e endpoints internos são autenticados; ausência de autenticação impede ação.
- **RNF-004:** erros externos geram estado consultável e não provocam perda dos dados originais.
- **RNF-005:** automações repetidas são idempotentes ou detectam duplicação.
- **RNF-006:** apenas dados sintéticos entram na demonstração; não publicar material restrito por NDA.
- **RNF-007:** cada ação relevante registra timestamp, evento e estado, sem dados sensíveis em excesso.
- **RNF-008:** o MVP terá testes automatizados para regras de negócio, contratos e fluxos de falha.

## 11. Critérios de aceitação (exemplos)

- **AC-001:** Dado formulário válido, quando o solicitante abre chamado, então é criado um ID único e o chamado fica consultável.
- **AC-002:** Dado chamado salvo, quando o n8n recebe o evento, então aciona endpoint de análise autenticado e registra a execução.
- **AC-003:** Dada análise estruturada válida, quando a API recebe o resultado, então salva categoria, resumo, prioridade sugerida e prioridade efetiva.
- **AC-004:** Dado chamado crítico ou ambíguo, quando a triagem termina, então o chamado fica disponível para revisão humana.
- **AC-005:** Dado serviço OpenAI indisponível, quando a análise falha, então o chamado continua consultável e o atendente pode tratá-lo manualmente.
- **AC-006:** Dado evento repetido, quando n8n o reprocessa, então não são criados chamados ou registros externos duplicados.
- **AC-007:** Dado atendimento resolvido, quando atendente registra solução e encerra, então estado `closed` e histórico ficam persistidos.
- **AC-008:** Dada ausência de credencial válida, quando serviço chama endpoint interno, então a solicitação é rejeitada.
- **AC-009:** Dada execução local limpa, quando usuário segue README, então consegue executar a demonstração e testes com dados sintéticos.

## 12. Entregáveis e critérios para concluir a Etapa 1

- [x] Objetivo e escopo descritos como proposta.
- [x] Atores e fluxo ponta a ponta descritos.
- [x] n8n definido como componente obrigatório de orquestração.
- [x] Requisitos, regras, estados e critérios de aceitação iniciais identificados.
- [x] Revisão humana do escopo concluída; nenhuma correção solicitada.
- [x] Aprovação explícita da Etapa 1 registrada em 2026-11-08.

**Próxima etapa autorizada para especificação:** modelagem do backend, banco, endpoints e mecanismo confiável para disparar o n8n. A execução de código permanece sujeita à revisão da arquitetura da Etapa 2.
