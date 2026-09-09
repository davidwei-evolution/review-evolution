# verify-core.ps1 - SHA-256 integrity check of the wb-review-evolution core
# without requiring Python. Uses the same CORE.json manifest as
# scripts/core_package.py verify. ASCII-only for PowerShell 5.1 safety.
param(
    [string]$CoreRoot = ''
)
$ErrorActionPreference = 'Stop'
if (-not $CoreRoot) { $CoreRoot = Join-Path $PSScriptRoot '..' }
$CoreRoot = [System.IO.Path]::GetFullPath($CoreRoot)
$manifestPath = Join-Path $CoreRoot 'CORE.json'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    Write-Error "Missing CORE.json: $manifestPath"
    exit 2
}
try {
    $meta = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Write-Error ('Invalid CORE.json: ' + $_.Exception.Message)
    exit 2
}
if ($meta.release_series -ne 'modular-1' -or $meta.data_schema -ne 1) {
    Write-Error 'Unsupported core metadata (release_series/data_schema).'
    exit 2
}
$manifest = @{}
foreach ($prop in $meta.files.PSObject.Properties) {
    $manifest[$prop.Name] = ([string]$prop.Value).ToLowerInvariant()
}
$actual = @{}
$extra = @()
Get-ChildItem -LiteralPath $CoreRoot -Recurse -File | ForEach-Object {
    $full = $_.FullName
    if ($full -like '*\__pycache__\*') { return }
    $rel = $full.Substring($CoreRoot.Length).TrimStart('\', '/').Replace('\', '/')
    if ($rel -eq 'CORE.json') { return }
    if ($manifest.ContainsKey($rel)) {
        $actual[$rel] = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
    } else {
        $extra += $rel
    }
}
$bad = @()
foreach ($rel in @($manifest.Keys | Sort-Object)) {
    if (-not $actual.ContainsKey($rel)) { $bad += "$rel  MISSING"; continue }
    if ($actual[$rel] -ne $manifest[$rel]) { $bad += "$rel  MISMATCH" }
}
foreach ($rel in @($extra | Sort-Object)) { $bad += "$rel  UNEXPECTED" }
Write-Output ("files=" + $manifest.Count + "  mismatches=" + $bad.Count + "  version=" + $meta.version + "  release_ready=" + $meta.release_ready)
foreach ($item in $bad) { Write-Output $item }
if ($bad.Count -gt 0) { exit 1 }
exit 0
