# Runs every chat pipeline over the Uzbek and Russian question sets (stt-eval\llm_compare). Re-runnable:
# finished result files are skipped. The chat server (port 8765) is restarted with CHAT_MODEL=<model>.
#   madlad  : MADLAD in -> model (English) -> MADLAD out            (current production design)
#   dual    : as madlad, model also sees the original text          (/api/chat dual_input=true)
#   hybrid  : model reads the original, answers in English -> MADLAD out (/api/chat direct_input=true)
#   direct  : model reads the original and answers in that language, no MADLAD
param([string[]]$Languages = @('uz', 'ru'), [switch]$NoThinking)
Set-Location (Split-Path $PSScriptRoot -Parent | Split-Path -Parent)
$py = '.\.venv-stt-eval\Scripts\python.exe'; $out = 'stt-eval\llm_compare\runs'
$env:PYTHONIOENCODING = 'utf-8'
New-Item -ItemType Directory -Force $out | Out-Null

function Restart-Chat($model) {
    $c = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
    if ($c) {
        $h = Invoke-RestMethod http://127.0.0.1:8765/api/health -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($h.model -eq $model -and $script:CodeFresh) { return }
        Stop-Process -Id $c[0].OwningProcess -Force; Start-Sleep 3
    }
    $env:CHAT_MODEL = $model
    Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList 'server.py' -WorkingDirectory (Get-Location) -WindowStyle Hidden `
        -RedirectStandardOutput logs\server.out.log -RedirectStandardError logs\server.err.log | Out-Null
    foreach ($i in 1..150) { Start-Sleep 2; try { $h = Invoke-RestMethod http://127.0.0.1:8765/api/health -TimeoutSec 3; if ($h.model -eq $model) { break } } catch {} }
    $script:CodeFresh = $true
    Write-Host ("[{0:HH:mm:ss}] chat server up with {1}" -f (Get-Date), $h.model)
}
function Run($pipeline, $name, $lang) {
    $file = "$out\$name.json"
    $expected = if ($lang -ne 'uz') { 20 } elseif ($pipeline -like 'direct-think:*') { 50 } else { 73 }
    if (Test-Path $file) {
        $n = ((Get-Content $file -Raw -Encoding UTF8 | ConvertFrom-Json).results).Count
        if ($n -ge $expected) { Write-Host "    skip (done) $name"; return }
    }
    Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $name)
    & $py -X utf8 stt-eval\scripts\llm_compare.py $pipeline $file $lang | Select-Object -Last 1
    $o = Get-CimInstance Win32_OperatingSystem
    Write-Host ("    free commit {0:N0} MB; ollama loaded: {1}" -f ($o.FreeVirtualMemory/1KB),
        (((Invoke-RestMethod http://127.0.0.1:11434/api/ps).models | ForEach-Object { "$($_.name) $([math]::Round($_.size/1GB,2))GB" }) -join ', '))
}

$script:CodeFresh = $false          # first restart always loads the current server.py
$models = @(@('qwen3:1.7b', 'qwen1.7b'), @('qwen3:4b-instruct', 'qwen4bi'), @('gemma3:4b', 'gemma4b'))
foreach ($lang in $Languages) {
    $sfx = if ($lang -eq 'uz') { '' } else { "_$lang" }
    foreach ($m in $models) {
        Restart-Chat $m[0]
        if ($lang -eq 'en') {
            # English never goes through MADLAD: the production path and the plain model call are the
            # only two distinct cases (performance baseline for each model)
            Run server "$($m[1])_server$sfx" $lang
            Run "direct:$($m[0])" "$($m[1])_direct$sfx" $lang
            continue
        }
        Run server        "$($m[1])_madlad$sfx" $lang
        Run server_dual   "$($m[1])_dual$sfx"   $lang
        Run server_direct "$($m[1])_hybrid$sfx" $lang
        Run "direct:$($m[0])" "$($m[1])_direct$sfx" $lang
    }
}
if (-not $NoThinking) {
    # Qwen3-4B-Thinking-2507 (tag qwen3:4b) with thinking enabled, answering directly (slow)
    foreach ($lang in $Languages) {
        $sfx = if ($lang -eq 'uz') { '' } else { "_$lang" }
        Run 'direct-think:qwen3:4b' "qwen4bthink_direct$sfx" $lang
    }
}
Restart-Chat 'qwen3:1.7b'
Write-Host ("[{0:HH:mm:ss}] all done" -f (Get-Date))
