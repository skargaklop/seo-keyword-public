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
Usage: auth_check.ps1 [--customer-id ID]

Checks OAuth + Google Ads access and runs a minimal SearchTermView query.
"@ | Write-Host
}

$customerId = ""
for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
  switch ($ScriptArguments[$i]) {
    "--customer-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --customer-id" }; $customerId = $ScriptArguments[++$i] }
    "-c" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -c" }; $customerId = $ScriptArguments[++$i] }
    "--help" { Show-Usage; exit 0 }
    "-h" { Show-Usage; exit 0 }
    default { Write-Error "Unknown option: $($ScriptArguments[$i])"; Show-Usage; exit 1 }
  }
}

[void](Load-GoogleAdsConfig)
if (-not $customerId) {
  $customerId = $Script:GoogleAdsConfig.GOOGLE_ADS_CUSTOMER_ID
} else {
  $customerId = Normalize-GoogleAdsCustomerId -Raw $customerId
}

Write-Host "[1/3] OAuth refresh"
[void](Get-GoogleAdsAccessToken)
Write-Host "OK"

Write-Host "[2/3] Accessible customers"
$resp = Invoke-GoogleAdsRequest -Method GET -Endpoint "customers:listAccessibleCustomers"
if (Test-GoogleAdsApiError -Payload $resp) {
  Write-GoogleAdsApiError -Payload $resp
  exit 1
}

$obj = $resp | ConvertFrom-Json
$names = @()
if ($obj.resourceNames) {
  $names = @($obj.resourceNames)
}
Write-Host ("Accessible customers: {0}" -f $names.Count)
$max = [Math]::Min(10, $names.Count)
for ($idx = 0; $idx -lt $max; $idx++) {
  Write-Host ("  - {0}" -f $names[$idx])
}

Write-Host "[3/3] SearchTermView smoke query"
$gaql = "SELECT search_term_view.search_term FROM search_term_view WHERE segments.date DURING LAST_7_DAYS LIMIT 1"
$body = @{ query = $gaql } | ConvertTo-Json -Compress
$resp2 = Invoke-GoogleAdsRequest -Method POST -Endpoint "customers/$customerId/googleAds:searchStream" -BodyJson $body
if (Test-GoogleAdsApiError -Payload $resp2) {
  Write-GoogleAdsApiError -Payload $resp2
  exit 1
}

$payload = $resp2 | ConvertFrom-Json
$chunks = @()
if ($payload -is [System.Array]) { $chunks = $payload } else { $chunks = @($payload) }

$count = 0
foreach ($chunk in $chunks) {
  if ($chunk.results) {
    $count += @($chunk.results).Count
  }
}

Write-Host ("SearchTermView rows fetched: {0}" -f $count)
Write-Host "Auth check completed successfully."


