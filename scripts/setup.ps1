$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "python is required"
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm is required"
}

Push-Location "$Root\backend"
python -m pip install -e ".[dev]"
Pop-Location

Push-Location "$Root\frontend"
npm install
Pop-Location
