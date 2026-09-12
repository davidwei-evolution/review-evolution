# re-cli.ps1 - Cross-shell launcher for wb-review-evolution (Windows PowerShell).
# Finds a usable Python (rejects the silent Microsoft Store stub and versions
# below 3.10), then runs scripts/experience.py with UTF-8 stdio.
# ASCII-only for PowerShell 5.1 safety.
param(
    [switch]$FindOnly,
    [switch]$InstallAll,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PassThru
)
$ErrorActionPreference = 'Stop'
$coreRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$scriptPath = Join-Path $coreRoot 'scripts\experience.py'

function Test-PythonVersionText {
    param([string]$Text)
    if ($Text -match 'PYOK ([0-9]+)\.([0-9]+)\.') {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        return ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10))
    }
    return $false
}

function Test-PythonCandidate {
    param([string]$Candidate)
    if (-not $Candidate) { return $null }
    if (-not (Test-Path -LiteralPath $Candidate)) { return $null }
    try {
        $output = & $Candidate -B -c "import sys;print('PYOK ' + sys.version.split()[0])" 2>&1
    } catch {
        return $null
    }
    $text = ($output | Out-String)
    if ($LASTEXITCODE -eq 0 -and (Test-PythonVersionText $text)) { return $Candidate }
    return $null
}

function Find-UsablePython {
    $override = $env:REVIEW_EVOLUTION_PYTHON
    if ($override) {
        $found = Test-PythonCandidate $override
        if ($found) { return $found }
    }
    $py = Get-Command 'py' -ErrorAction SilentlyContinue
    if ($py -and $py.Source) {
        try {
            $output = & $py.Source -3 -c "import sys;print('PYOK ' + sys.version.split()[0])" 2>&1
        } catch {
            $output = $null
        }
        $text = ($output | Out-String)
        if ($LASTEXITCODE -eq 0 -and (Test-PythonVersionText $text)) { return $py.Source }
    }
    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd -or -not $cmd.Source) { continue }
        $found = Test-PythonCandidate $cmd.Source
        if ($found) { return $found }
    }
    $pythonBase = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path -LiteralPath $pythonBase) {
        $dirs = @(Get-ChildItem -LiteralPath $pythonBase -Directory -Filter 'Python3*' | Sort-Object Name -Descending)
        foreach ($dir in $dirs) {
            $found = Test-PythonCandidate (Join-Path $dir.FullName 'python.exe')
            if ($found) { return $found }
        }
    }
    return $null
}

$python = Find-UsablePython
if (-not $python) {
    [Console]::Error.WriteLine('[re-cli] No usable Python found.')
    [Console]::Error.WriteLine('Python 3.10+ is required; the Microsoft Store placeholder and older versions are rejected.')
    [Console]::Error.WriteLine('Install official Python first, e.g.:')
    [Console]::Error.WriteLine('  winget install --id Python.Python.3.12 --source winget --scope user')
    [Console]::Error.WriteLine('If Python was just installed, restart the client so PATH is refreshed.')
    [Console]::Error.WriteLine('Without Python only files-only install and verify-core.ps1 are available.')
    exit 3
}
if ($FindOnly) {
    Write-Output $python
    exit 0
}
if ($InstallAll) {
    # D1 (2026-09-12): one call instead of verify/init/bind/status/doctor, so a host that
    # asks per command has one thing to authorize. Whether it really asks only once is the
    # host's decision, not this script's - never promise a single prompt.
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    Write-Host '[install] step 1/4: verifying skill files (read-only)...'
    & $python -B (Join-Path $coreRoot 'scripts\core_package.py') verify
    if ($LASTEXITCODE -ne 0) {
        [Console]::Error.WriteLine('[install] core verification failed. Nothing was changed.')
        exit 1
    }
    $base = $env:LOCALAPPDATA
    if (-not $base) { $base = Join-Path $env:USERPROFILE 'AppData\Local' }
    $dataRoot = Join-Path $base 'review-evolution'
    $installation = Join-Path $dataRoot 'installation.json'
    Write-Host '[install] step 2/4: checking for an existing local binding (never overwritten)...'
    $bound = $null
    if (Test-Path -LiteralPath $installation) {
        try {
            $bound = (Get-Content -LiteralPath $installation -Raw -Encoding UTF8 | ConvertFrom-Json).profile_root
        } catch {
            $bound = $null
        }
    }
    if ($bound) {
        Write-Host ('[install] existing profile found; reusing it and NOT creating a new one: ' + $bound)
    } else {
        $profileRoot = Join-Path $dataRoot 'profiles\default'
        Write-Host '[install] step 3/4: no binding yet; preparing a private profile...'
        Write-Host ('[install]   target: ' + $profileRoot)
        if (-not (Test-Path -LiteralPath (Join-Path $profileRoot 'profile.json'))) {
            & $python -B $scriptPath --profile $profileRoot init
            if ($LASTEXITCODE -ne 0) {
                [Console]::Error.WriteLine('[install] profile init failed. Nothing else was changed.')
                exit 1
            }
        }
        & $python -B $scriptPath bind $profileRoot
        if ($LASTEXITCODE -ne 0) {
            [Console]::Error.WriteLine('[install] binding failed. The profile itself is kept.')
            exit 1
        }
    }
    Write-Host '[install] step 4/4: read-only self check (doctor)...'
    & $python -B $scriptPath doctor
    $code = $LASTEXITCODE
    Write-Host '[install] done. Your experience archive stays on this machine; nothing is uploaded.'
    Write-Host '[install] You can now ask: "what have you remembered about me?"'
    exit $code
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
& $python -B $scriptPath @PassThru
exit $LASTEXITCODE
