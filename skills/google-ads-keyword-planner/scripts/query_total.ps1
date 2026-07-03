[CmdletBinding(PositionalBinding = $false)]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ScriptArguments
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($null -eq $ScriptArguments) {
  $ScriptArguments = @()
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "common.ps1")

function Show-Usage {
  @"
Usage: query_total.ps1 --phrase "(a|b) keyword" [--regions "2840"] [--language-id "1000"]

Requires Google Ads credentials in config/.env:
  GOOGLE_ADS_DEVELOPER_TOKEN
  GOOGLE_ADS_CLIENT_ID
  GOOGLE_ADS_CLIENT_SECRET
  GOOGLE_ADS_REFRESH_TOKEN
  GOOGLE_ADS_CUSTOMER_ID
  GOOGLE_ADS_LOGIN_CUSTOMER_ID (optional)
  GOOGLE_ADS_API_VERSION (optional, default v22)
"@ | Write-Host
}

$phrase = ""
$regions = ""
$languageId = "1000"
$maxKeywords = "500"

for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
  $arg = $ScriptArguments[$i]
  switch ($arg) {
    "--phrase" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --phrase" }; $phrase = $ScriptArguments[++$i] }
    "-p" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -p" }; $phrase = $ScriptArguments[++$i] }
    "--regions" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --regions" }; $regions = $ScriptArguments[++$i] }
    "-r" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -r" }; $regions = $ScriptArguments[++$i] }
    "--language-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --language-id" }; $languageId = $ScriptArguments[++$i] }
    "--max-keywords" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --max-keywords" }; $maxKeywords = $ScriptArguments[++$i] }
    "--help" { Show-Usage; exit 0 }
    "-h" { Show-Usage; exit 0 }
    default { Write-Error "Unknown option: $arg"; Show-Usage; exit 1 }
  }
}

if (-not $phrase) {
  Write-Error "Error: --phrase is required."
  Show-Usage
  exit 1
}

[void](Load-GoogleAdsConfig)

$cmd = @(
  "uv", "run", "--script", (Join-Path $scriptDir "missed_demand.py"), "query-total",
  "--developer-token", $Script:GoogleAdsConfig.GOOGLE_ADS_DEVELOPER_TOKEN,
  "--client-id", $Script:GoogleAdsConfig.GOOGLE_ADS_CLIENT_ID,
  "--client-secret", $Script:GoogleAdsConfig.GOOGLE_ADS_CLIENT_SECRET,
  "--refresh-token", $Script:GoogleAdsConfig.GOOGLE_ADS_REFRESH_TOKEN,
  "--customer-id", $Script:GoogleAdsConfig.GOOGLE_ADS_CUSTOMER_ID,
  "--api-version", (Get-GoogleAdsApiVersion),
  "--phrase", $phrase,
  "--language-id", $languageId,
  "--max-keywords", $maxKeywords
)

if ($Script:GoogleAdsConfig.GOOGLE_ADS_LOGIN_CUSTOMER_ID) {
  $cmd += @("--login-customer-id", $Script:GoogleAdsConfig.GOOGLE_ADS_LOGIN_CUSTOMER_ID)
}

if ($regions) {
  $cmd += @("--regions", $regions)
}

& $cmd[0] $cmd[1..($cmd.Count - 1)]
exit $LASTEXITCODE

