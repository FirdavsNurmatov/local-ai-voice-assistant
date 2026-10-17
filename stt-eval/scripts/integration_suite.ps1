# Runs the fixed integration test set against a running STT TEST instance and stores every response.
# usage: powershell -File stt-eval\scripts\integration_suite.ps1 -Out <dir> [-Base http://127.0.0.1:8779] [-UzOnly]
param([Parameter(Mandatory = $true)][string]$Out, [string]$Base = 'http://127.0.0.1:8779', [switch]$UzOnly, [switch]$SkipExisting, [switch]$AllowProductionPort)
Set-Location (Split-Path $PSScriptRoot -Parent | Split-Path -Parent)
if ($Base -match ':8769' -and -not $AllowProductionPort) { throw 'Refusing to test against the production port 8769 (use -AllowProductionPort deliberately).' }
$py = '.\.venv-stt-eval\Scripts\python.exe'; $t = 'stt-eval\scripts\integration_test.py'; $d = 'stt-eval\datasets'
$env:PYTHONIOENCODING = 'utf-8'
New-Item -ItemType Directory -Force $Out | Out-Null
function Invoke-Set($ds, $lang, $name, $extra = '') {
    if ($SkipExisting -and (Test-Path "$Out\$name.json")) { Write-Host "== skip (done) $name"; return }
    Write-Host ("== {0:HH:mm:ss} {1}" -f (Get-Date), $name)
    & $py -X utf8 $t $Base "$d\$ds.csv" $lang "$Out\$name.json" $extra
}
if (-not $UzOnly) {
    # language handling as the page sends it today ("Avto" = no parameter)
    Invoke-Set ruen_formats none ruen_auto
    Invoke-Set ruen_formats none ruen_auto_multipart multipart
    Invoke-Set ru_formats ru ru_forced
    Invoke-Set en_formats en en_forced
    Invoke-Set edge none edge_auto
    Invoke-Set fleurs_parity none uz_etalon_auto
    Invoke-Set fleurs_uz_holdout none uz_holdout_auto
    Invoke-Set uz_commands_synthetic none uz_commands_auto
}
# Uzbek forced (the path that would move to NavAI)
Invoke-Set edge uz edge_uz
Invoke-Set fleurs_parity uz uz_etalon_uz
Invoke-Set fleurs_uz_holdout uz uz_holdout_uz
Invoke-Set uz_commands_synthetic uz uz_commands_uz
Invoke-Set uz_commands_synthetic uz uz_commands_uz_multipart multipart
Invoke-Set synthetic_uz uz uz_synthetic_uz
Write-Host ("== {0:HH:mm:ss} done" -f (Get-Date))
