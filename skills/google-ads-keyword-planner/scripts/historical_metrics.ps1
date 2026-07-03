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
Usage: historical_metrics.ps1 --keywords "k1,k2" [options]

Options:
  --keywords, -k       Comma-separated keywords (required).
  --language-id        Google Ads language ID (default: 1000).
  --geo-ids            Comma-separated geo target IDs.
  --customer-id, -c    Override GOOGLE_ADS_CUSTOMER_ID.
  --output             Save raw JSON response to file.
  --help, -h           Show this help.
"@ | Write-Host
}

$keywordsCsv = ""
$languageId = "1000"
$geoIds = ""
$customerId = ""
$outputFile = ""

for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
  $arg = $ScriptArguments[$i]
  switch ($arg) {
    "--keywords" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --keywords" }; $keywordsCsv = $ScriptArguments[++$i] }
    "-k" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -k" }; $keywordsCsv = $ScriptArguments[++$i] }
    "--language-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --language-id" }; $languageId = $ScriptArguments[++$i] }
    "--geo-ids" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --geo-ids" }; $geoIds = $ScriptArguments[++$i] }
    "--customer-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --customer-id" }; $customerId = $ScriptArguments[++$i] }
    "-c" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -c" }; $customerId = $ScriptArguments[++$i] }
    "--output" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --output" }; $outputFile = $ScriptArguments[++$i] }
    "--help" { Show-Usage; exit 0 }
    "-h" { Show-Usage; exit 0 }
    default { Write-Error "Unknown option: $arg"; Show-Usage; exit 1 }
  }
}

if (-not $keywordsCsv) {
  Write-Error "Error: --keywords is required."
  Show-Usage
  exit 1
}

[void](Load-GoogleAdsConfig)
if (-not $customerId) {
  $customerId = $Script:GoogleAdsConfig.GOOGLE_ADS_CUSTOMER_ID
} else {
  $customerId = Normalize-GoogleAdsCustomerId -Raw $customerId
}

$keywords = @($keywordsCsv.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })

$body = [ordered]@{
  keywords = $keywords
  language = "languageConstants/$languageId"
  includeAdultKeywords = $false
}

$geoList = @()
if ($geoIds) {
  $geoList = @($geoIds.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
if ($geoList.Count -gt 0) {
  $body.geoTargetConstants = @($geoList | ForEach-Object { "geoTargetConstants/$_" })
}

$payload = $body | ConvertTo-Json -Depth 20 -Compress
$response = Invoke-GoogleAdsRequest -Method POST -Endpoint "customers/$customerId`:generateKeywordHistoricalMetrics" -BodyJson $payload
if (Test-GoogleAdsApiError -Payload $response) {
  Write-GoogleAdsApiError -Payload $response
  exit 1
}

if ($outputFile) {
  Set-Content -LiteralPath $outputFile -Value $response -Encoding UTF8
  Write-Host "Saved raw response to: $outputFile"
}

$obj = $response | ConvertFrom-Json
$results = @()
if ($obj.results) {
  $results = @($obj.results)
}

if ($results.Count -eq 0) {
  Write-Host "No historical metrics returned."
  exit 0
}

Write-Host ("Historical metrics rows: {0}" -f $results.Count)
Write-Host "| # | Keyword | Avg monthly searches | Competition |"
Write-Host "|---|---------|----------------------|-------------|"

$index = 0
foreach ($row in $results) {
  $index++
  $text = [string]$row.text
  $metrics = $row.keywordMetrics
  $avg = if ($metrics.avgMonthlySearches) { [int64]$metrics.avgMonthlySearches } else { 0 }
  $comp = if ($metrics.competition) { [string]$metrics.competition } else { "UNKNOWN" }
  Write-Host ("| {0} | {1} | {2} | {3} |" -f $index, $text, $avg, $comp)
}


