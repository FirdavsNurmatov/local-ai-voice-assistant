# Robot command label test for every model and input mode (stt-eval\llm_compare\commands). Needs only Ollama.
Set-Location (Split-Path $PSScriptRoot -Parent | Split-Path -Parent)
$py = '.\.venv-stt-eval\Scripts\python.exe'; $out = 'stt-eval\llm_compare\commands'
$env:PYTHONIOENCODING = 'utf-8'
$models = @(@('qwen3:1.7b', 'qwen1.7b'), @('qwen3:4b-instruct', 'qwen4bi'), @('gemma3:4b', 'gemma4b'))
foreach ($m in $models) {
    foreach ($mode in 'madlad', 'dual', 'original') {
        $file = "$out\$($m[1])_$mode.json"
        if (Test-Path $file) { Write-Host "    skip (done) $file"; continue }
        & $py -X utf8 stt-eval\scripts\command_compare.py $m[0] $mode $file | Select-Object -Last 1
    }
}
# the thinking model (qwen3:4b) is tested on questions only (owner's decision: too slow for commands)
Write-Host ("[{0:HH:mm:ss}] commands done" -f (Get-Date))
