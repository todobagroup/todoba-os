# TODOBA Startup Launcher
#
# Starts TODOBA Executor
# Designed for Windows startup / always-on runtime

$TODABA_ROOT = "E:\TODOBA OS\todoba-os"

Set-Location $TODABA_ROOT

& ".\.venv\Scripts\Activate.ps1"

python -m backend.start_executor