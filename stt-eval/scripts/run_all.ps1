# Runs the whole evaluation sequentially (one model per process). Safe to re-run; existing outputs are overwritten.
# usage:  powershell -ExecutionPolicy Bypass -File stt-eval\scripts\run_all.ps1 [-Gpu]
param([switch]$Gpu, [switch]$CpuOnly, [switch]$PostHoc, [int]$CoolDownSeconds = 0)   # e.g. -CoolDownSeconds 60 to rest the CPU between runs
$ErrorActionPreference = 'Continue'
Set-Location (Split-Path $PSScriptRoot -Parent | Split-Path -Parent)          # project root
$py = '.\.venv-stt-eval\Scripts\python.exe'
$run = 'stt-eval\scripts\run_config.py'
$ds = 'stt-eval\datasets'; $out = 'stt-eval\runs'
$env:PYTHONIOENCODING = 'utf-8'
if ($Gpu) {
    $nv = Resolve-Path '.venv-stt-eval\Lib\site-packages\nvidia'
    $env:PATH = ((Get-ChildItem $nv -Recurse -Directory -Filter bin | ForEach-Object FullName) -join ';') + ';' + $env:PATH
}
function Invoke-Cfg($dataset, $cfg, $lang, $dev = 'cpu', $limit = '') {
    $f = "$out\${dataset}__${cfg}__${lang}__${dev}.json"
    if (Test-Path $f) { Write-Host ("[{0:HH:mm:ss}] skip (done) {1}" -f (Get-Date), (Split-Path $f -Leaf)); return }
    Write-Host ("[{0:HH:mm:ss}] {1} {2} {3} {4}" -f (Get-Date), $dataset, $cfg, $lang, $dev)
    & $py -X utf8 -W ignore $run $cfg $lang "$ds\$dataset.csv" $f $dev $limit 2>&1 | Where-Object { $_ -notmatch 'Warning|warn\(|^\s*$' } | ForEach-Object { "    $_" }
    if ($CoolDownSeconds -gt 0) { Start-Sleep -Seconds $CoolDownSeconds }
}
if (-not $Gpu -and -not $PostHoc) {
    # A. real human speech (FLEURS uz test sample) - primary comparison, language forced to uz
    foreach ($c in 'small_prod', 'navai_prod', 'small_neutral', 'navai_neutral') { Invoke-Cfg fleurs_uz_test_sample $c uz }
    # A'. diagnostic: automatic language detection through the production rule
    foreach ($c in 'small_prod', 'navai_prod') { Invoke-Cfg fleurs_uz_test_sample $c auto }
    # conversion parity: CT2 int8 greedy vs original Transformers/PyTorch fp32 greedy
    Invoke-Cfg fleurs_parity navai_card uz; Invoke-Cfg fleurs_parity hf_navai uz
    # B. synthetic Uzbek (diagnostic only)
    foreach ($c in 'small_prod', 'navai_prod', 'small_neutral', 'navai_neutral') { Invoke-Cfg synthetic_uz $c uz }
    foreach ($c in 'small_prod', 'navai_prod') { Invoke-Cfg synthetic_uz $c auto }
    # C. Russian / English regression (synthetic)
    foreach ($l in 'ru', 'en') {
        foreach ($c in 'small_prod', 'navai_prod') { Invoke-Cfg "regression_$l" $c auto; Invoke-Cfg "regression_$l" $c $l }
    }
}
if ($PostHoc) {
    # D. post-hoc variant chosen after inspecting test-set errors (decode without timestamp tokens).
    #    Reported separately from the unbiased comparison A.
    Invoke-Cfg fleurs_parity navai_card_nots uz
    foreach ($c in 'navai_neutral_nots', 'small_neutral_nots') { Invoke-Cfg fleurs_uz_test_sample $c uz }
    foreach ($c in 'navai_neutral_nots', 'small_neutral_nots') { Invoke-Cfg synthetic_uz $c uz }
}
if ($Gpu -and -not $CpuOnly) {
    foreach ($c in 'small_neutral', 'navai_neutral') { Invoke-Cfg fleurs_uz_test_sample $c uz cuda }
}
Write-Host ("[{0:HH:mm:ss}] done" -f (Get-Date))

