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
Usage: health_check.ps1 [--customer-id ID]

Checks:
  1) OAuth refresh token exchange
  2) customers:listAccessibleCustomers
  3) Basic GAQL query against selected customer
"@ | Write-Host
}

$customerId = ""

if ($ScriptArguments) {
  for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
    $arg = $ScriptArguments[$i]
    switch ($arg) {
      "--customer-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --customer-id" }; $customerId = $ScriptArguments[++$i] }
      "-c" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -c" }; $customerId = $ScriptArguments[++$i] }
      "--help" { Show-Usage; exit 0 }
      "-h" { Show-Usage; exit 0 }
      default { Write-Error "Unknown option: $arg"; Show-Usage; exit 1 }
    }
  }
}

[void](Load-GoogleAdsConfig)
if (-not $customerId) {
  $customerId = $Script:GoogleAdsConfig.GOOGLE_ADS_CUSTOMER_ID
}
else {
  $customerId = Normalize-GoogleAdsCustomerId -Raw $customerId
}

Write-Host "[1/3] Checking OAuth refresh..."
$accessToken = Get-GoogleAdsAccessToken
if (-not $accessToken) {
  Write-Error "Error: failed to get access token."
  exit 1
}
Write-Host "OAuth refresh: OK"

Write-Host "[2/3] Calling customers:listAccessibleCustomers..."
$accessibleResponse = Invoke-GoogleAdsRequest -Method GET -Endpoint "customers:listAccessibleCustomers"
if (Test-GoogleAdsApiError -Payload $accessibleResponse) {
  Write-GoogleAdsApiError -Payload $accessibleResponse
  exit 1
}

$accessibleObj = $accessibleResponse | ConvertFrom-Json
$customers = @()
if ($accessibleObj.resourceNames) {
  $customers = @($accessibleObj.resourceNames)
}

Write-Host ("Accessible customers: {0}" -f $customers.Count)
$preview = [Math]::Min(20, $customers.Count)
for ($idx = 0; $idx -lt $preview; $idx++) {
  Write-Host ("  - {0}" -f $customers[$idx])
}
if ($customers.Count -gt 20) {
  Write-Host ("  ... and {0} more" -f ($customers.Count - 20))
}

Write-Host "[3/3] Running GAQL smoke query..."
$gaql = "SELECT customer.id, customer.descriptive_name FROM customer LIMIT 1"
$body = @{ query = $gaql } | ConvertTo-Json -Compress
$queryResponse = Invoke-GoogleAdsRequest -Method POST -Endpoint "customers/$customerId/googleAds:searchStream" -BodyJson $body
if (Test-GoogleAdsApiError -Payload $queryResponse) {
  Write-GoogleAdsApiError -Payload $queryResponse
  exit 1
}

$payload = $queryResponse | ConvertFrom-Json
$chunks = @()
if ($payload -is [System.Array]) {
  $chunks = $payload
}
else {
  $chunks = @($payload)
}

$rows = @()
foreach ($chunk in $chunks) {
  if ($chunk.results) {
    foreach ($row in $chunk.results) {
      $cid = $row.customer.id
      $name = $row.customer.descriptiveName
      $rows += [PSCustomObject]@{ Id = $cid; Name = $name }
    }
  }
}

if ($rows.Count -eq 0) {
  Write-Host "GAQL smoke query: no rows returned"
}
else {
  foreach ($r in $rows) {
    Write-Host ("GAQL smoke query: OK ({0} / {1})" -f $r.Id, $r.Name)
  }
}

Write-Host "Health check completed successfully."


