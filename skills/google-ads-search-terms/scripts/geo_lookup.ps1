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
Usage: geo_lookup.ps1 [--query TEXT] [--geo-ids 2840,2250] [options]

Options:
  --query, -q          Name fragment for geo target lookup.
  --geo-ids            Comma-separated geo target IDs.
  --country-code       Country code filter (e.g. RU, US).
  --limit              Max rows (default: 30).
  --customer-id, -c    Override GOOGLE_ADS_CUSTOMER_ID.
  --help, -h           Show this help.
"@ | Write-Host
}

$queryText = ""
$geoIds = ""
$countryCode = ""
$limit = 30
$customerId = ""

for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
  $arg = $ScriptArguments[$i]
  switch ($arg) {
    "--query" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --query" }; $queryText = $ScriptArguments[++$i] }
    "-q" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -q" }; $queryText = $ScriptArguments[++$i] }
    "--geo-ids" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --geo-ids" }; $geoIds = $ScriptArguments[++$i] }
    "--country-code" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --country-code" }; $countryCode = $ScriptArguments[++$i] }
    "--limit" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --limit" }; $limit = [int]$ScriptArguments[++$i] }
    "--customer-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --customer-id" }; $customerId = $ScriptArguments[++$i] }
    "-c" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -c" }; $customerId = $ScriptArguments[++$i] }
    "--help" { Show-Usage; exit 0 }
    "-h" { Show-Usage; exit 0 }
    default { Write-Error "Unknown option: $arg"; Show-Usage; exit 1 }
  }
}

if (-not $queryText -and -not $geoIds) {
  Write-Error "Error: set --query or --geo-ids."
  Show-Usage
  exit 1
}

[void](Load-GoogleAdsConfig)
if (-not $customerId) {
  $customerId = $Script:GoogleAdsConfig.GOOGLE_ADS_CUSTOMER_ID
}
else {
  $customerId = Normalize-GoogleAdsCustomerId -Raw $customerId
}

$parts = New-Object System.Collections.Generic.List[string]
$parts.Add("SELECT")
$parts.Add("  geo_target_constant.id,")
$parts.Add("  geo_target_constant.name,")
$parts.Add("  geo_target_constant.country_code,")
$parts.Add("  geo_target_constant.target_type,")
$parts.Add("  geo_target_constant.status")
$parts.Add("FROM geo_target_constant")
$parts.Add("WHERE geo_target_constant.status = 'ENABLED'")

if ($queryText) {
  $safe = $queryText.Replace("'", "''")
  $parts.Add("AND geo_target_constant.name LIKE '%$safe%'")
}

if ($countryCode) {
  $cc = $countryCode.Trim().ToUpperInvariant()
  $parts.Add("AND geo_target_constant.country_code = '$cc'")
}

if ($geoIds) {
  $ids = @($geoIds.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  if ($ids.Count -gt 0) {
    $parts.Add("AND geo_target_constant.id IN ($($ids -join ','))")
  }
}

$limit = [Math]::Max(1, $limit)
$parts.Add("LIMIT $limit")
$gaql = $parts -join "`n"

$body = @{ query = $gaql } | ConvertTo-Json -Compress
$response = Invoke-GoogleAdsRequest -Method POST -Endpoint "customers/$customerId/googleAds:searchStream" -BodyJson $body
if (Test-GoogleAdsApiError -Payload $response) {
  Write-GoogleAdsApiError -Payload $response
  exit 1
}

$payload = $response | ConvertFrom-Json
$chunks = @()
if ($payload -is [System.Array]) {
  $chunks = $payload
}
else {
  $chunks = @($payload)
}

$rows = New-Object System.Collections.Generic.List[object]
foreach ($chunk in $chunks) {
  if (-not $chunk.results) {
    continue
  }

  foreach ($row in $chunk.results) {
    $geo = $row.geoTargetConstant
    $rows.Add([PSCustomObject]@{
      id = $geo.id
      name = $geo.name
      country_code = $geo.countryCode
      target_type = $geo.targetType
      status = $geo.status
    })
  }
}

if ($rows.Count -eq 0) {
  Write-Host "No geo targets found."
  exit 0
}

Write-Host ("Found geo targets: {0}" -f $rows.Count)
Write-Host "| ID | Name | Country | Type | Status |"
Write-Host "|----|------|---------|------|--------|"
foreach ($row in $rows) {
  Write-Host ("| {0} | {1} | {2} | {3} | {4} |" -f $row.id, $row.name, $row.country_code, $row.target_type, $row.status)
}
