[CmdletBinding(PositionalBinding = $false)]
param(
  [string]$Keyword = "",
  [string]$LanguageId = "1000",
  [string]$GeoIds = "",
  [int]$Months = 12,
  [string]$CustomerId = "",
  [string]$Output = "",
  [Alias("h")][switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "common.ps1")

function Show-Usage {
  @"
Usage: search_volume.ps1 -Keyword "k1[,k2]" [options]

Options:
  -Keyword            Comma-separated keywords (required).
  -LanguageId         Google Ads language ID (default: 1000).
  -GeoIds             Comma-separated geo target IDs.
  -Months             Number of recent months to show (default: 12).
  -CustomerId         Override GOOGLE_ADS_CUSTOMER_ID.
  -Output             Save raw JSON response to file.
  --help, -h          Show this help.
"@ | Write-Host
}

if ($Help) {
  Show-Usage
  exit 0
}

if (-not $Keyword) {
  Write-Error "Error: -Keyword is required."
  Show-Usage
  exit 1
}

[void](Load-GoogleAdsConfig)
if (-not $CustomerId) {
  $CustomerId = $Script:GoogleAdsConfig.GOOGLE_ADS_CUSTOMER_ID
}
else {
  $CustomerId = Normalize-GoogleAdsCustomerId -Raw $CustomerId
}

$keywords = @($Keyword.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($keywords.Count -eq 0) {
  Write-Error "Error: no valid keywords provided."
  exit 1
}

$body = [ordered]@{
  keywords             = $keywords
  language             = "languageConstants/$LanguageId"
  includeAdultKeywords = $false
}

$geoList = @()
if ($GeoIds) {
  $geoList = @($GeoIds.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
if ($geoList.Count -gt 0) {
  $body.geoTargetConstants = @($geoList | ForEach-Object { "geoTargetConstants/$_" })
}

$payload = $body | ConvertTo-Json -Depth 20 -Compress
$response = Invoke-GoogleAdsRequest -Method POST -Endpoint "customers/$CustomerId`:generateKeywordHistoricalMetrics" -BodyJson $payload
if (Test-GoogleAdsApiError -Payload $response) {
  Write-GoogleAdsApiError -Payload $response
  exit 1
}

if ($Output) {
  Set-Content -LiteralPath $Output -Value $response -Encoding UTF8
  Write-Host "Saved raw response to: $Output"
}

$obj = $response | ConvertFrom-Json
$results = @()
if ($obj.PSObject.Properties["results"]) {
  $results = @($obj.results)
}

if ($results.Count -eq 0) {
  Write-Host "No historical metrics returned."
  exit 0
}

if ($Months -lt 1) {
  $Months = 1
}

foreach ($row in $results) {
  $text = [string](Get-ObjectPropertyValue -Object $row -Name "text")
  $metrics = Get-ObjectPropertyValue -Object $row -Name "keywordMetrics"
  $avg = Get-ObjectPropertyValue -Object $metrics -Name "avgMonthlySearches"
  if ($null -eq $avg) { $avg = 0 }
  $comp = Get-ObjectPropertyValue -Object $metrics -Name "competition"
  if ($null -eq $comp -or "$comp" -eq "") { $comp = "UNKNOWN" }
  $monthly = @()
  $monthlyRaw = Get-ObjectPropertyValue -Object $metrics -Name "monthlySearchVolumes"
  if ($monthlyRaw) {
    $monthly = @($monthlyRaw)
  }

  Write-Host ""
  Write-Host ("=== {0} ===" -f $text)
  Write-Host ("Avg monthly searches: {0} | Competition: {1}" -f $avg, $comp)

  if ($monthly.Count -eq 0) {
    Write-Host "No monthly breakdown available."
    continue
  }

  $recent = @($monthly | Select-Object -Last $Months)
  Write-Host ""
  Write-Host ("Monthly volumes (last {0} months):" -f $recent.Count)
  Write-Host "| Year | Month | Searches |"
  Write-Host "|------|-------|----------|"
  foreach ($entry in $recent) {
    $year = Get-ObjectPropertyValue -Object $entry -Name "year"
    $month = [string](Get-ObjectPropertyValue -Object $entry -Name "month")
    $monthLabel = $month -replace "MONTH_", "" -replace "_", " "
    $searches = Get-ObjectPropertyValue -Object $entry -Name "monthlySearches"
    if ($null -eq $searches) { $searches = 0 }
    Write-Host ("| {0} | {1} | {2} |" -f $year, $monthLabel, $searches)
  }
}
