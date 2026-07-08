param(
    [Parameter(Mandatory=$true)]
    [string[]]$Inputs,

    [string]$OutDir = "output",
    [int]$Limit = 0,
    [switch]$WriteEvents
)

$ErrorActionPreference = "Stop"
$Project = Split-Path -Parent $PSScriptRoot
$Py311 = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
$VenvPython = Join-Path $Project ".venv_ml\Scripts\python.exe"
$S2Protocol = Join-Path $Project "external\s2protocol"

Set-Location $Project

if (!(Test-Path $Py311)) {
    throw "Python 3.11 was not found at $Py311. Install Python 3.11 or edit this script's `$Py311 path."
}

if (!(Test-Path $VenvPython)) {
    Write-Host "Creating ML virtual environment with Python 3.11..."
    & $Py311 -m venv (Join-Path $Project ".venv_ml")
}

Write-Host "Installing Python dependencies..."
& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -r (Join-Path $Project "requirements.txt")

if (!(Test-Path (Join-Path $Project "external"))) {
    New-Item -ItemType Directory -Path (Join-Path $Project "external") | Out-Null
}

if (!(Test-Path $S2Protocol)) {
    Write-Host "Cloning Blizzard s2protocol..."
    git clone https://github.com/Blizzard/s2protocol.git $S2Protocol
}

Write-Host "Installing s2protocol into ML venv..."
& $VenvPython -m pip install -e $S2Protocol

$env:PYTHONPATH = Join-Path $Project "src"

$IngestArgs = @("-m", "aok_ml.ingest_replays") + $Inputs + @("--out", $OutDir)
if ($Limit -gt 0) { $IngestArgs += @("--limit", "$Limit") }
if ($WriteEvents) { $IngestArgs += "--write-events" }

Write-Host "Parsing replays..."
& $VenvPython @IngestArgs

Write-Host "Mining strategy summaries..."
& $VenvPython -m aok_ml.strategy_miner --out $OutDir

Write-Host "Training readable ML models..."
& $VenvPython -m aok_ml.train_models --out $OutDir

Write-Host ""
Write-Host "Done. Outputs are in: $(Join-Path $Project $OutDir)"
Write-Host "Main guide: $(Join-Path $Project "$OutDir\guides\aok_team_roles_and_timing_windows_guide.md")"
