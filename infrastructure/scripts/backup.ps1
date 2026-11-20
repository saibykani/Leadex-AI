# Dump the postgres container database into .\backups\<db>_<timestamp>.sql
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root
$user = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "leadex" }
$db = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "leadex" }
New-Item -ItemType Directory -Force "backups" | Out-Null
$out = Join-Path $Root ("backups\{0}_{1}.sql" -f $db, (Get-Date -Format "yyyyMMdd_HHmmss"))
# Redirect via cmd so PowerShell 5.1 does not re-encode the dump as UTF-16.
cmd /c "docker compose exec -T postgres pg_dump -U $user -d $db --clean --if-exists --no-owner > `"$out`""
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed" }
Write-Host "Backup written to $out"
