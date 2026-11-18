# Segurança e limitações do MVP local

O AI Support Flow é destinado a **demonstração local com dados sintéticos**. Não publicar a configuração atual em host público.

## Proteções existentes

- `ASF_INTERNAL_SERVICE_KEY` é requerido nas rotas de análise e callback de sincronização.
- `N8N_WEBHOOK_KEY` protege o webhook do n8n; `N8N_ENCRYPTION_KEY` cifra as credenciais armazenadas pelo n8n.
- Chave OpenAI permanece no backend; `frontend` usa proxy HTTP, sem segredos no código enviado ao navegador.
- Outbox e transações SQLite diminuem perda de eventos; históricos preservam decisões humanas.
- Saída da IA passa por schema estruturado e regras de domínio; o texto do chamado é tratado como entrada não confiável.
- `store=False` na chamada Responses API reduz persistência solicitada ao provedor, mas não constitui promessa universal de retenção zero.

## Limites importantes

- `X-Demo-Role: attendant` é **falsificável** e não é autenticação/autorização segura.
- As rotas CRUD públicas locais não têm autenticação; nunca expor a API aberta para acesso externo.
- `N8N_SECURE_COOKIE=false` funciona somente na demonstração sem HTTPS. Em hospedagem pública seria inadequado.
- SQLite local e dispatcher simples não entregam garantias para múltiplas réplicas em produção.
- O uso de *upsert* no Sheets não garante ausência absoluta de duplicações concorrentes.
- Retentativas de Outbox em `dead_letter` necessitam procedimento operacional.
- O projeto não possui ainda política de privacidade, retenção formal, limitação de acesso por organização ou observabilidade exigidas para serviço real.

## Antes de fazer push

1. Não versionar `.env` nem qualquer arquivo `.env.*` com valores reais, exceto `.env.example` com placeholders.
2. Não versionar bancos (`*.sqlite*`, `*.db`), dumps, backups, volumes `.n8n`, chaves privadas ou credenciais Google.
3. Não versionar `backend/.venv-stage8`, `node_modules`, `frontend/dist`, `_etapa8` ou outras pastas temporárias.
4. Revisar capturas, nomes, emails, tokens e URLs privados manualmente.
5. Executar `scripts/check-publication.ps1` (Windows) ou `bash scripts/check-publication.sh` (Linux/macOS) e revisar a lista de arquivos a incluir no commit.
6. Se uma chave foi acidentalmente adicionada ao Git, **rotacione-a**, remova-a do histórico antes de publicar e não confie somente no `.gitignore`.

## Chaves e nomes de modelos

Um exemplo de modelo configurado não deve ser interpretado como recomendação permanente nem garantia de acesso. O arquivo `.env.example` usa `AI_MODE=mock` por padrão; no arquivo `.env` privado configure modelos disponíveis e apropriados à sua conta.
