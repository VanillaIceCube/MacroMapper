param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\certs")
)

$ErrorActionPreference = "Stop"
$certificateDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $certificateDirectory -Force | Out-Null

$certificatePath = Join-Path $certificateDirectory "origin.pem"
$privateKeyPath = Join-Path $certificateDirectory "origin.key"

if (Get-Command mkcert -ErrorAction SilentlyContinue) {
    & mkcert -cert-file $certificatePath -key-file $privateKeyPath `
        "fullstacktemplate.localhost" "localhost" "127.0.0.1" "::1"
    if ($LASTEXITCODE -ne 0) {
        throw "mkcert could not generate the local certificate."
    }
    Write-Output "Created a locally trusted certificate for fullstacktemplate.localhost."
    exit 0
}

if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
    throw "Install mkcert (recommended) or OpenSSL, then run this script again."
}

& openssl req -x509 -nodes -newkey rsa:2048 -sha256 -days 365 `
    -keyout $privateKeyPath `
    -out $certificatePath `
    -subj "/CN=fullstacktemplate.localhost" `
    -addext "subjectAltName=DNS:fullstacktemplate.localhost,DNS:localhost,IP:127.0.0.1,IP:::1" `
    -config NUL

if ($LASTEXITCODE -ne 0) {
    throw "OpenSSL could not generate the local certificate."
}

Write-Warning "Created a self-signed certificate. The browser will warn until you trust certs/origin.pem."
