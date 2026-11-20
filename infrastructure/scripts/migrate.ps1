# Apply all Alembic migrations (uses MIGRATION_DATABASE_URL (schema owner) from the environment / .env).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..\apps\api")
$alembic = ".\.venv\Scripts\alembic.exe"
if (-not (Test-Path $alembic)) { $alembic = "alembic" }
& $alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed" }
