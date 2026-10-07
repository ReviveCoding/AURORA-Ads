param([string]$ReportRoot = "$PSScriptRoot/../reports/environment")
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $ReportRoot | Out-Null
$commands = @(
    @{name='codex'; exe='codex'; args=@('--version')},
    @{name='wsl_version'; exe='wsl'; args=@('--version')},
    @{name='wsl_distros'; exe='wsl'; args=@('--list','--verbose')},
    @{name='wsl_inventory'; exe='wsl'; args=@('-d','Ubuntu-22.04','--','bash','-lc','python3 --version; df -B1 /; free -b; nproc; uname -a')},
    @{name='gpu'; exe='nvidia-smi'; args=@('--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw,pstate','--format=csv')},
    @{name='gpu_processes'; exe='nvidia-smi'; args=@('--query-compute-apps=pid,process_name,used_memory','--format=csv')}
)
$records = @()
foreach ($entry in $commands) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $output = & $entry.exe @($entry.args) 2>&1 | Out-String
    $code = $LASTEXITCODE
    $watch.Stop()
    $records += @{command=@($entry.exe)+$entry.args; output=$output.Replace("`0",''); exit_code=$code; wall_seconds=$watch.Elapsed.TotalSeconds; name=$entry.name}
}
$os = Get-CimInstance Win32_OperatingSystem
$computer = Get-CimInstance Win32_ComputerSystem
$drive = Get-PSDrive C
$manifest = Get-Content "$PSScriptRoot/../PACKAGE_MANIFEST.json" -Raw | ConvertFrom-Json
$hashes = foreach ($entry in $manifest.files) {
    $file = Join-Path "$PSScriptRoot/.." $entry.path
    $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    @{path=$entry.path; expected_sha256=$entry.sha256; actual_sha256=$actual; matches=($actual -eq $entry.sha256)}
}
$result = @{measured_at_utc=[DateTime]::UtcNow.ToString('o'); powershell=$PSVersionTable.PSVersion.ToString(); host_ram_total_bytes=[long]$os.TotalVisibleMemorySize*1024; host_ram_available_bytes=[long]$os.FreePhysicalMemory*1024; host_cpu_count=$computer.NumberOfLogicalProcessors; backing_free_bytes=$drive.Free; commands=$records; preparation_manifest_audit=$hashes; gpu_health='NOT_QUALIFIED'; heavy_workload_absence='NOT_YET_ESTABLISHED'}
$temp = Join-Path $ReportRoot 'inventory.tmp.json'
$target = Join-Path $ReportRoot ("E00_"+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffff')+'.json')
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temp -Encoding utf8
Move-Item -LiteralPath $temp -Destination $target
Write-Output $target
