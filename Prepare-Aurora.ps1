#requires -Version 7.0
<# Verify and install the small design bundle into a NEW directory, then prepare WSL.
   With -StartCodex, open an empty native interactive Codex session. Never run codex exec. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BundlePath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256,
    [string]$RepoRoot = 'C:\Users\bjw-0\Downloads\AURORA-Ads',
    [string]$Distribution = 'Ubuntu-22.04',
    [switch]$StartCodex,
    [switch]$CopyMasterPrompt
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false

function Assert-NoReparse([string]$Path) {
    $p = [System.IO.Path]::GetFullPath($Path)
    while ($p) {
        if (Test-Path -LiteralPath $p) {
            $item = Get-Item -LiteralPath $p -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Reparse-point path: $p" }
        }
        $parent = [System.IO.Directory]::GetParent($p)
        if ($null -eq $parent) { break }
        $p = $parent.FullName
    }
}
function Assert-SafeRelative([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name) -or $Name -match '[\\:\*\?<>|"\x00-\x1f]' -or $Name.StartsWith('/')) {
        throw 'Unsafe archive path.'
    }
    foreach ($part in $Name.Split('/')) {
        if ($part -in @('', '.', '..') -or $part -match '[. ]$' -or $part -match '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)') {
            throw 'Unsafe or nonportable archive component.'
        }
    }
}

if (-not $IsWindows) { throw 'Use PowerShell 7 on Windows.' }
$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
$BundlePath = [System.IO.Path]::GetFullPath($BundlePath)
if ($RepoRoot -ne 'C:\Users\bjw-0\Downloads\AURORA-Ads') { throw 'The repository destination is pinned by the design.' }
Assert-NoReparse $RepoRoot
Assert-NoReparse $BundlePath
if (Test-Path -LiteralPath $RepoRoot) {
    throw 'Destination already exists. It was not changed. Use its Start-Aurora.ps1, or reconcile it manually before installing.'
}
if (-not (Test-Path -LiteralPath $BundlePath -PathType Leaf)) { throw 'Bundle not found.' }
$parent = [System.IO.Directory]::GetParent($RepoRoot).FullName
if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'Expected Downloads directory is absent.' }
$actual = (Get-FileHash -LiteralPath $BundlePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedSha256.ToLowerInvariant()) { throw 'ZIP SHA-256 mismatch. No destination was created.' }
$codex = Get-Command codex -ErrorAction Stop | Select-Object -First 1
$helpText = (& $codex.Source --help 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $helpText -notmatch '--approve-for-me' -or $helpText -notmatch '--strict-config') {
    throw 'Codex required approval flags are unavailable. No installation or permission downgrade was attempted.'
}
$strictVersion = (& $codex.Source --strict-config --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Codex strict-config preflight failed. No repository was created.' }
$git = Get-Command git -ErrorAction Stop | Select-Object -First 1
$wsl = Get-Command wsl.exe -ErrorAction Stop
$distros = ((& $wsl.Source --list --quiet 2>&1 | Out-String) -replace "`0", '') -split "\r?\n"
if ($LASTEXITCODE -ne 0 -or $Distribution -notin @($distros | ForEach-Object { $_.Trim() })) { throw 'Requested WSL distribution is absent.' }
$drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($RepoRoot))
if ($drive.AvailableFreeSpace -lt 20GB) { throw 'Less than 20 GiB free on the Windows backing volume.' }

$staging = Join-Path $parent ('.aurora-prep-' + [guid]::NewGuid().ToString('N'))
[void][System.IO.Directory]::CreateDirectory($staging)
$archive = $null
try {
    $archive = [System.IO.Compression.ZipFile]::OpenRead($BundlePath)
    if ($archive.Entries.Count -gt 1000) { throw 'Archive member count exceeds the design-bundle limit.' }
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    [long]$total = 0
    foreach ($entry in $archive.Entries) {
        $name = $entry.FullName.TrimEnd('/')
        Assert-SafeRelative $name
        if ($name -ne 'AURORA-Ads' -and -not $name.StartsWith('AURORA-Ads/', [System.StringComparison]::Ordinal)) {
            throw 'Unexpected archive root.'
        }
        if (-not $seen.Add($name)) { throw 'Duplicate or case-colliding archive path.' }
        $unixType = ($entry.ExternalAttributes -shr 16) -band 0xf000
        if ($unixType -eq 0xa000 -or (($entry.ExternalAttributes -band 0x400) -ne 0)) { throw 'Archive links/reparse entries are refused.' }
        $total += $entry.Length
        if ($total -gt 20MB -or $entry.Length -gt 5MB) { throw 'Design bundle exceeds extraction quota.' }
        $destination = [System.IO.Path]::GetFullPath((Join-Path $staging $name))
        if (-not $destination.StartsWith($staging + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Archive path escapes staging.'
        }
        if ($entry.FullName.EndsWith('/')) { [void][System.IO.Directory]::CreateDirectory($destination); continue }
        [void][System.IO.Directory]::CreateDirectory([System.IO.Directory]::GetParent($destination).FullName)
        $inputStream = $entry.Open()
        $outputStream = [System.IO.File]::Open($destination, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try {
            $buffer = [byte[]]::new(65536)
            [long]$written = 0
            while (($read = $inputStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $written += $read
                if ($written -gt $entry.Length -or $written -gt 5MB) { throw 'Expanded payload exceeds declared length.' }
                $outputStream.Write($buffer, 0, $read)
            }
            $outputStream.Flush($true)
        } finally { $outputStream.Dispose(); $inputStream.Dispose() }
        if ((Get-Item -LiteralPath $destination).Length -ne $entry.Length) { throw 'Extracted file-size mismatch.' }
    }
    $archive.Dispose(); $archive = $null
    $sourceRoot = Join-Path $staging 'AURORA-Ads'
    $manifestPath = Join-Path $sourceRoot 'PACKAGE_MANIFEST.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $listed = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($f in $manifest.files) {
        Assert-SafeRelative $f.path
        if (-not $listed.Add($f.path)) { throw 'Duplicate manifest path.' }
        $p = Join-Path $sourceRoot $f.path
        if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Manifest file absent: $($f.path)" }
        if ((Get-Item -LiteralPath $p).Length -ne [long]$f.bytes) { throw 'Manifest size mismatch.' }
        if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ne $f.sha256) { throw 'Manifest hash mismatch.' }
    }
    $actualFiles = @(Get-ChildItem -LiteralPath $sourceRoot -File -Recurse -Force)
    if ($actualFiles.Count -ne ($listed.Count + 1)) { throw 'Unlisted payload files present.' }
    foreach ($f in $actualFiles) {
        $rel = [System.IO.Path]::GetRelativePath($sourceRoot, $f.FullName).Replace('\', '/')
        if ($rel -ne 'PACKAGE_MANIFEST.json' -and -not $listed.Contains($rel)) { throw 'Unexpected payload file.' }
    }
    # Same-volume rename into a path which must still be absent; do not merge or overwrite.
    if (Test-Path -LiteralPath $RepoRoot) { throw 'Destination appeared during preparation; preserved.' }
    [System.IO.Directory]::Move($sourceRoot, $RepoRoot)
    [System.IO.Directory]::Delete($staging, $false)
} catch {
    Write-Warning "Preparation stopped. Any partial new staging files are preserved at $staging. No existing project was deleted."
    throw
} finally { if ($null -ne $archive) { $archive.Dispose() } }

# Initialize only this new repository, with an empty template. No add/commit/push or global Git edits.
$template = Join-Path $RepoRoot '.local\empty-git-template'
[void][System.IO.Directory]::CreateDirectory($template)
& $git.Source init "--template=$template" -- $RepoRoot
if ($LASTEXITCODE -ne 0) { throw 'Git initialization failed. The verified design directory was preserved.' }
$startScript = Join-Path $RepoRoot 'Start-Aurora.ps1'
# The extracted launcher is already hash-verified. Remove only its downloaded-file mark if present; do not alter machine execution policy.
Unblock-File -LiteralPath $startScript -ErrorAction SilentlyContinue
if ($CopyMasterPrompt) {
    $promptPath = Join-Path $RepoRoot 'MASTER_PROMPT.md'
    if (-not (Test-Path -LiteralPath $promptPath -PathType Leaf)) { throw 'Verified MASTER_PROMPT.md is missing.' }
    Get-Content -LiteralPath $promptPath -Raw | Set-Clipboard
    Write-Host 'Verified MASTER_PROMPT.md copied to clipboard. Paste it into Codex and press Enter when ready.'
}
& $startScript -RepoRoot $RepoRoot -Distribution $Distribution -PrepareOnly:(-not $StartCodex)
