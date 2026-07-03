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
Usage: keyword_ideas.ps1 --seed "query" [options]

Options:
  --seed, -s           Seed keyword. Repeat flag or pass comma-separated list.
  --url                Landing page URL for URL seed.
  --language-id        Google Ads language ID (default: 1000).
  --geo-ids            Comma-separated geo target IDs.
  --page-size          Number of ideas (default: 50).
  --customer-id, -c    Override GOOGLE_ADS_CUSTOMER_ID.
  --output             Save raw JSON response to file.
  --help, -h           Show this help.
"@ | Write-Host
}

$seeds = New-Object System.Collections.Generic.List[string]
$seedUrl = ""
$languageId = "1000"
$geoIds = ""
$pageSize = 50
$outputFile = ""
$customerId = ""

for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
  $arg = $ScriptArguments[$i]
  switch ($arg) {
    "--seed" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --seed" }; $seeds.Add($ScriptArguments[++$i]) }
    "-s" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -s" }; $seeds.Add($ScriptArguments[++$i]) }
    "--url" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --url" }; $seedUrl = $ScriptArguments[++$i] }
    "--language-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --language-id" }; $languageId = $ScriptArguments[++$i] }
    "--geo-ids" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --geo-ids" }; $geoIds = $ScriptArguments[++$i] }
    "--page-size" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --page-size" }; $pageSize = [int]$ScriptArguments[++$i] }
    "--output" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --output" }; $outputFile = $ScriptArguments[++$i] }
    "--customer-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --customer-id" }; $customerId = $ScriptArguments[++$i] }
    "-c" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -c" }; $customerId = $ScriptArguments[++$i] }
    "--help" { Show-Usage; exit 0 }
    "-h" { Show-Usage; exit 0 }
    default { Write-Error "Unknown option: $arg"; Show-Usage; exit 1 }
  }
}

if ($seeds.Count -eq 0 -and -not $seedUrl) {
  Write-Error "Error: at least one --seed or --url is required."
  Show-Usage
  exit 1
}

[void](Load-GoogleAdsConfig)
if (-not $customerId) {
  $customerId = $Script:GoogleAdsConfig.GOOGLE_ADS_CUSTOMER_ID
} else {
  $customerId = Normalize-GoogleAdsCustomerId -Raw $customerId
}

$body = [ordered]@{
  language = "languageConstants/$languageId"
  keywordPlanNetwork = "GOOGLE_SEARCH_AND_PARTNERS"
  pageSize = [Math]::Max(1, [int]$pageSize)
  includeAdultKeywords = $false
}

$geoList = @()
if ($geoIds) {
  $geoList = @($geoIds.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
if ($geoList.Count -gt 0) {
  $body.geoTargetConstants = @($geoList | ForEach-Object { "geoTargetConstants/$_" })
}

if ($seeds.Count -gt 0 -and $seedUrl) {
  $body.keywordAndUrlSeed = @{ keywords = @($seeds); url = $seedUrl }
} elseif ($seeds.Count -gt 0) {
  $body.keywordSeed = @{ keywords = @($seeds) }
} else {
  $body.urlSeed = @{ url = $seedUrl }
}

$payload = $body | ConvertTo-Json -Depth 20 -Compress
$response = Invoke-GoogleAdsRequest -Method POST -Endpoint "customers/$customerId`:generateKeywordIdeas" -BodyJson $payload
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
  Write-Host "No keyword ideas returned."
  exit 0
}

Write-Host ("Keyword ideas: {0}" -f $results.Count)
Write-Host "| # | Keyword | Avg monthly searches | Competition | Low bid | High bid |"
Write-Host "|---|---------|----------------------|-------------|---------|----------|"

$index = 0
foreach ($row in $results) {
  $index++
  $text = [string](Get-ObjectPropertyValue -Object $row -Name "text")
  $metrics = Get-ObjectPropertyValue -Object $row -Name "keywordIdeaMetrics"

  $avg = Get-ObjectPropertyValue -Object $metrics -Name "avgMonthlySearches"
  if ($null -eq $avg) { $avg = 0 } else { $avg = [int64]$avg }

  $comp = Get-ObjectPropertyValue -Object $metrics -Name "competition"
  if ($null -eq $comp -or "$comp" -eq "") { $comp = "UNKNOWN" }

  $low = Get-ObjectPropertyValue -Object $metrics -Name "lowTopOfPageBidMicros"
  if ($null -eq $low) { $low = 0 } else { $low = [int64]$low }

  $high = Get-ObjectPropertyValue -Object $metrics -Name "highTopOfPageBidMicros"
  if ($null -eq $high) { $high = 0 } else { $high = [int64]$high }

  Write-Host ("| {0} | {1} | {2} | {3} | {4} | {5} |" -f $index, $text, $avg, $comp, $low, $high)
}


