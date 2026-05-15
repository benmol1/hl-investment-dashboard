# Load .env into the current session and run a Python script via uv.
# Usage: .\run_local.ps1 backend/scripts/download_transactions.py
#        .\run_local.ps1 backend/scripts/fetch_prices.py

param([Parameter(Mandatory)][string]$Script)

Get-Content .env |
    Where-Object { $_ -match '^\s*[^#]\S+=\S+' } |
    ForEach-Object {
        $k, $v = $_ -split '=', 2
        [System.Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim())
    }

uv run python $Script
