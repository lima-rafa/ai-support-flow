# Verificador conservador, somente leitura, para uso local antes do git add/push.
# Não lê nem mostra conteúdo de segredos. Complementa, mas não substitui, revisão manual.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    Write-Host "Revisao pre-publicacao - AI Support Flow" -ForegroundColor Cyan
    $sensitive = @(
      '.env', 'backend/.env', 'frontend/.env',
      'asf-backup-v02.sqlite', 'backend/.venv-stage8',
      'frontend/node_modules', 'frontend/dist',
      'frontend/_etapa8', '_etapa8'
    )
    $git = Get-Command git -ErrorAction SilentlyContinue
    foreach ($item in $sensitive) {
        $exists = Test-Path -LiteralPath $item
        $ignored = 'indisponivel (sem git)'
        if ($git) {
            & git check-ignore -q -- $item 2>$null
            $ignored = if ($LASTEXITCODE -eq 0) { 'sim' } else { 'nao/nao se aplica' }
        }
        Write-Host ("{0,-32} existe={1,-5} ignorado={2}" -f $item, $exists, $ignored)
    }
    if ($git) {
        & git rev-parse --is-inside-work-tree *> $null
        if ($LASTEXITCODE -eq 0) {
            $tracked = @(& git ls-files)
            $flags = $tracked | Where-Object { $_ -match '(^|/)(\.env($|\.)|\.venv|node_modules|_etapa\d+|\.n8n|.*\.sqlite(?:-.*)?$|.*\.db$|asf-backup|credentials.*\.json$)' }
            if ($flags) {
                Write-Warning 'Possiveis arquivos sensiveis JA RASTREADOS (inspecione):'
                $flags | ForEach-Object { Write-Host "  $_" }
            } else { Write-Host 'Nenhum caminho de alto risco identificado entre arquivos rastreados.' -ForegroundColor Green }
            Write-Host 'Revise MANUALMENTE os arquivos preparados com git diff --cached --name-only.'
        } else { Write-Host 'Ainda nao ha repositorio Git nesta pasta.' }
    } else { Write-Warning 'Git nao localizado no PATH; verifique manualmente antes de publicar.' }
    Write-Host 'ATENCAO: este script nao detecta chaves inseridas dentro de arquivos fonte.' -ForegroundColor Yellow
} finally { Pop-Location }
