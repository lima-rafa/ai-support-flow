# Publicação segura do AI Support Flow no GitHub (Windows e Linux)

**Atenção:** estas etapas **não publicam automaticamente** nenhum arquivo. Você mantém controle sobre o `git commit` e o `git push`.

## 1. Trabalhe na pasta correta

A **raiz oficial do repositório Git é `ai-support-flow/`**, contendo `backend/`, `frontend/`, `docs/`, `scripts/`, `n8n/` e `compose.yaml`. No Windows, ela pode estar dentro da pasta externa `AI-SUPPORT-FLOW-ETAPA-3-v0.2/`, mas essa pasta externa **não** entra no repositório. Não copie um `.env` para outra árvore apenas para publicar o código. Não rode `docker compose down -v`.

```powershell
Get-Location
git --version
npm --version
```

## 2. Conferir conteúdo e build

```powershell
cd frontend
npm install
npm run build
cd ..
```

Se o build falhar, corrija antes de apresentar o repositório. Para testes Python, com o ambiente `backend/.venv-stage8` já instalado:

```powershell
cd backend
.\.venv-stage8\Scripts\python.exe -m pytest -q
cd ..
```

## 3. Revisão de segurança

Na raiz:

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check-publication.ps1
```

Linux/macOS (Bash):

```bash
bash ./scripts/check-publication.sh
```


O script confere padrões conhecidos de arquivos sensíveis e mostra sua condição de ignore. **Não substitui revisão humana**, nem detecta segredos colados dentro de código fonte. Revise os textos em `docs/evidence/` e o arquivo `n8n/workflows/WF-001-ticket-triage.json` para garantir que nenhum ID/credencial privada foi incluído.

## 4. Iniciar repositório sem publicar

Se `git status` disser que não existe repositório:

```powershell
git init
git branch -M main
```

Depois, **antes de adicionar arquivos**, revise candidatos:

```powershell
git status --short --untracked-files=all
git add -n .
```

Se estiver seguro:

```powershell
git add .
git status --short
git diff --cached --name-only
```

Confirme que `.env`, `asf-backup-v02.sqlite`, `.venv-stage8`, `node_modules`, tokens, chaves e dumps **não aparecem** nos arquivos preparados. Se um arquivo sensível tiver sido rastreado anteriormente, `.gitignore` **não o retira do índice**: use `git rm --cached <arquivo>` e considere rotacionar qualquer segredo já exposto.

## 5. Commit e repositório remoto

Somente quando os arquivos preparados estiverem corretos:

```powershell
git commit -m "docs: documentar MVP AI Support Flow e evidencias de testes"
```

Crie um repositório **vazio** no GitHub (sem README/licença inicial, pois esses arquivos estarão no seu projeto). Depois use a URL HTTPS que o GitHub apresentar:

```powershell
git remote add origin https://github.com/SEU-USUARIO/ai-support-flow.git
git push -u origin main
```

**O endereço acima é apenas um exemplo:** substitua pelo URL real do seu repositório. O push só deve ocorrer após auditoria e revisão explícita dos arquivos. Se o projeto já possui `origin`, confira `git remote -v` em vez de adicionar outro.

## 6. Verificações finais

- README renderizado corretamente com Mermaid e links relativos.
- Nenhum segredo, token, SQLite ou arquivo local publicado.
- README reflete validações reais; resultados ainda pendentes não aparecem como aprovados.
- Opcional: adicionar capturas sanitizadas à pasta `docs/evidence` e links no README.
- Opcional: criar uma release/tópicos no GitHub após demonstração final.

## 7. Política de licença

Nenhuma licença é presumida neste pacote. A escolha de licença aberta (MIT, Apache-2.0 etc.) depende de sua decisão e da origem de todos os materiais utilizados. Na ausência de licença, o código publicado não recebe automaticamente uma autorização ampla de reutilização.

## Execucao em Linux/macOS

A partir de `ai-support-flow/`, utilize `cp .env.example .env` somente em **instalacao nova**, `docker compose up -d --build`, `curl http://127.0.0.1:8000/health` e `bash ./scripts/check-publication.sh` para a verificacao pre-publicacao. Para o frontend, `cd frontend && npm install && npm run build`; para os testes Python, utilize um ambiente virtual separado, com `python3 -m venv .venv-stage8`, `./.venv-stage8/bin/python -m pip install -r requirements-dev.txt` e `./.venv-stage8/bin/python -m pytest -q` dentro de `backend/`.
