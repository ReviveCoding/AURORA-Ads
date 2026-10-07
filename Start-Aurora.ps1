#requires -Version 7.0
<# Prepare the declared WSL runtime, then open native interactive Codex without an initial prompt.
   No package installation, downloads, GPU workloads, global configuration edits, or ad actions. #>
[CmdletBinding()]
param(
    [string]$RepoRoot = 'C:\Users\bjw-0\Downloads\AURORA-Ads',
    [string]$Distribution = 'Ubuntu-22.04',
    [switch]$PrepareOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

function Assert-NoReparse([string]$Path) {
    $p = [System.IO.Path]::GetFullPath($Path)
    while ($p) {
        if (Test-Path -LiteralPath $p) {
            $item = Get-Item -LiteralPath $p -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Reparse-point path not accepted: $p"
            }
        }
        $parent = [System.IO.Directory]::GetParent($p)
        if ($null -eq $parent) { break }
        $p = $parent.FullName
    }
}

if (-not $IsWindows) { throw 'Run this launcher in PowerShell 7 on Windows.' }
$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
if ($RepoRoot -ne 'C:\Users\bjw-0\Downloads\AURORA-Ads') {
    throw 'This design is pinned to C:\Users\bjw-0\Downloads\AURORA-Ads.'
}
Assert-NoReparse $RepoRoot
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'docs\FINAL_SPEC.md') -PathType Leaf)) {
    throw 'Install the verified AURORA v2 bundle first.'
}
$codex = Get-Command codex -ErrorAction Stop | Select-Object -First 1
$helpText = (& $codex.Source --help 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $helpText -notmatch '--approve-for-me' -or $helpText -notmatch '--strict-config') {
    throw 'This Codex CLI does not expose the required flags. No full-access fallback is permitted.'
}
$codexVersion = (& $codex.Source --strict-config --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Codex strict-config preflight failed. No sandbox or approval fallback was attempted.' }
$wsl = Get-Command wsl.exe -ErrorAction Stop
$distros = ((& $wsl.Source --list --quiet 2>&1 | Out-String) -replace "`0", '') -split "\r?\n"
if ($LASTEXITCODE -ne 0 -or $Distribution -notin @($distros | ForEach-Object { $_.Trim() })) {
    throw "WSL distribution unavailable: $Distribution. The launcher will not install or replace it."
}
$drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($RepoRoot))
if ($drive.AvailableFreeSpace -lt 20GB) { throw 'Windows backing volume has less than 20 GiB free reserve.' }
# Pass the canonical Windows repo through WSLENV so WSL performs path translation.
# Calling wslpath directly from PowerShell can lose backslashes before the Linux command sees them.
$oldWSLENV = $env:WSLENV
$oldAuroraRepoWin = $env:AURORA_REPO_WIN
try {
    $env:AURORA_REPO_WIN = $RepoRoot
    $wslEnvEntry = 'AURORA_REPO_WIN/p'
    $wslEnvParts = @()
    if (-not [string]::IsNullOrWhiteSpace($env:WSLENV)) {
        $wslEnvParts = @($env:WSLENV -split ':')
    }
    if ($wslEnvParts -notcontains $wslEnvEntry) {
        $env:WSLENV = if ($wslEnvParts.Count -eq 0) { $wslEnvEntry } else { (($wslEnvParts + $wslEnvEntry) -join ':') }
    }
    $repoLinux = (& $wsl.Source -d $Distribution -- printenv AURORA_REPO_WIN 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoLinux) -or -not $repoLinux.StartsWith('/')) {
        throw 'Cannot translate the canonical Windows repository path through WSLENV.'
    }
} finally {
    if ($null -eq $oldWSLENV) { Remove-Item Env:WSLENV -ErrorAction SilentlyContinue } else { $env:WSLENV = $oldWSLENV }
    if ($null -eq $oldAuroraRepoWin) { Remove-Item Env:AURORA_REPO_WIN -ErrorAction SilentlyContinue } else { $env:AURORA_REPO_WIN = $oldAuroraRepoWin }
}
& $wsl.Source -d $Distribution -- test -d $repoLinux
if ($LASTEXITCODE -ne 0) {
    throw "WSL cannot access the canonical repository at: $repoLinux"
}
# Native Python is only used here for small standard-library filesystem checks.
$runtimeOutput = (& $wsl.Source -d $Distribution -- python3 "$repoLinux/tools/prepare_runtime.py" --repo $repoLinux --apply 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "WSL preparation blocked. Existing files were preserved. Details: $runtimeOutput" }
$runtime = $runtimeOutput | ConvertFrom-Json -AsHashtable
$local = Join-Path $RepoRoot '.local'
Assert-NoReparse $local
[void][System.IO.Directory]::CreateDirectory($local)
$record = [ordered]@{
    status = 'PREPARED_AWAITING_IMPLEMENTATION_PROMPT'
    recorded_at = [DateTimeOffset]::Now.ToString('o')
    powershell_version = $PSVersionTable.PSVersion.ToString()
    codex_version = $codexVersion
    distribution = $Distribution
    repo_windows = $RepoRoot
    repo_wsl = $repoLinux
    runtime = $runtime
    approval_mode = 'approve-for-me'
    sandbox = 'workspace-write'
    initial_prompt_supplied = $false
    dependency_installation = 'NOT_ATTEMPTED'
    gpu_qualification = 'NOT_RUN'
    experiments_launched = $false
}
$recordPath = Join-Path $local 'preparation.json'
Assert-NoReparse $recordPath
$tmp = Join-Path $local ('preparation.' + [guid]::NewGuid().ToString('N') + '.tmp')
[System.IO.File]::WriteAllText($tmp, ($record | ConvertTo-Json -Depth 10), [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::Move($tmp, $recordPath, $true)
Write-Host "Prepared: $RepoRoot"
Write-Host "Runtime: $($runtime.runtime_wsl)"
Write-Host 'No data/model downloads, ML dependency installs, training, or GPU qualification were performed.'
if ($PrepareOnly) {
    Write-Host 'Stopped before Codex. Run this launcher without -PrepareOnly to open the interactive input.'
    return
}
Write-Host 'Opening native interactive Codex with Approve for me. No implementation prompt is supplied.'
Write-Host 'Login, workspace trust, managed-policy constraints, or an auto-review denial may still require your attention.'
Push-Location -LiteralPath $RepoRoot
try {
    & $codex.Source --approve-for-me --strict-config --cd $RepoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Codex exited with code $LASTEXITCODE. Approval and sandbox settings were not weakened."
    }
} finally { Pop-Location }
