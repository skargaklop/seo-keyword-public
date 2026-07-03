Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
@"
Use geo_lookup.ps1 with Google Ads geo target constants.
Examples:
  powershell -ExecutionPolicy Bypass -File scripts/geo_lookup.ps1 --query "Russia" --limit 20
  powershell -ExecutionPolicy Bypass -File scripts/geo_lookup.ps1 --geo-ids 2840
"@ | Write-Host
