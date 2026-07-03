Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
@"
get_token.ps1 is removed in Google Ads mode.
Use config/README.md to obtain OAuth refresh token and place values in config/.env.
"@ | Write-Host
