# One-time local setup: .env (random JWT_SECRET), api venv + dev deps, web deps.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Root

if (-not (Test-Path ".env")) {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    $content = (Get-Content ".env.example") -replace '^JWT_SECRET=.*', "JWT_SECRET=$secret"
    [System.IO.File]::WriteAllLines((Join-Path $Root ".env"), $content)
    Write-Host "Created .env with a random JWT_SECRET"
} else {
    Write-Host ".env already exists; leaving it unchanged"
}

Set-Location (Join-Path $Root "apps\api")
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Set-Location (Join-Path $Root "apps\web")
npm install
if ($LASTEXITCODE -ne 0) { throw "npm install failed" }

Set-Location $Root
Write-Host "Setup complete."
