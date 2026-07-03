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
Usage: search_terms_sync.ps1 [options]

Options:
  --date-from           Start date YYYY-MM-DD (default: 30 days ago)
  --date-to             End date YYYY-MM-DD (default: today)
  --campaign-ids        Comma-separated campaign IDs
  --status              Search term status filter (ADDED|EXCLUDED|ADDED_EXCLUDED|NONE)
  --limit               Limit rows (default: 1000)
  --customer-id, -c     Override GOOGLE_ADS_CUSTOMER_ID
  --output              Save JSON rows to file
  --quiet               Do not print table summary
  --help, -h            Show this help
"@ | Write-Host
}

$dateFrom = ""
$dateTo = ""
$campaignIds = ""
$statusFilter = ""
$limit = 1000
$customerId = ""
$outputFile = ""
$quiet = $false

for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
  $arg = $ScriptArguments[$i]
  switch ($arg) {
    "--date-from" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --date-from" }; $dateFrom = $ScriptArguments[++$i] }
    "--date-to" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --date-to" }; $dateTo = $ScriptArguments[++$i] }
    "--campaign-ids" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --campaign-ids" }; $campaignIds = $ScriptArguments[++$i] }
    "--status" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --status" }; $statusFilter = $ScriptArguments[++$i] }
    "--limit" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --limit" }; $limit = [int]$ScriptArguments[++$i] }
    "--customer-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --customer-id" }; $customerId = $ScriptArguments[++$i] }
    "-c" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -c" }; $customerId = $ScriptArguments[++$i] }
    "--output" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --output" }; $outputFile = $ScriptArguments[++$i] }
    "--quiet" { $quiet = $true }
    "--help" { Show-Usage; exit 0 }
    "-h" { Show-Usage; exit 0 }
    default { Write-Error "Unknown option: $arg"; Show-Usage; exit 1 }
  }
}

[void](Load-GoogleAdsConfig)
if (-not $customerId) {
  $customerId = $Script:GoogleAdsConfig.GOOGLE_ADS_CUSTOMER_ID
} else {
  $customerId = Normalize-GoogleAdsCustomerId -Raw $customerId
}

if (-not $dateFrom -or -not $dateTo) {
  $today = Get-Date
  $start = $today.AddDays(-30)
  if (-not $dateFrom) { $dateFrom = $start.ToString("yyyy-MM-dd") }
  if (-not $dateTo) { $dateTo = $today.ToString("yyyy-MM-dd") }
}

$parts = New-Object System.Collections.Generic.List[string]
$parts.Add("SELECT")
$parts.Add("  search_term_view.search_term,")
$parts.Add("  search_term_view.status,")
$parts.Add("  campaign.id,")
$parts.Add("  campaign.name,")
$parts.Add("  ad_group.id,")
$parts.Add("  ad_group.name,")
$parts.Add("  metrics.impressions,")
$parts.Add("  metrics.clicks,")
$parts.Add("  metrics.cost_micros,")
$parts.Add("  metrics.conversions")
$parts.Add("FROM search_term_view")
$parts.Add("WHERE segments.date BETWEEN '$dateFrom' AND '$dateTo'")

if ($campaignIds) {
  $ids = @($campaignIds.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  if ($ids.Count -gt 0) {
    $parts.Add("AND campaign.id IN ($($ids -join ','))")
  }
}

if ($statusFilter) {
  $status = $statusFilter.Trim().ToUpperInvariant()
  $parts.Add("AND search_term_view.status = '$status'")
}

$parts.Add("ORDER BY metrics.impressions DESC")
$parts.Add("LIMIT $([Math]::Max(1, $limit))")
$gaql = $parts -join "`n"

$body = @{ query = $gaql } | ConvertTo-Json -Compress
$response = Invoke-GoogleAdsRequest -Method POST -Endpoint "customers/$customerId/googleAds:searchStream" -BodyJson $body
if (Test-GoogleAdsApiError -Payload $response) {
  Write-GoogleAdsApiError -Payload $response
  exit 1
}

$payload = $response | ConvertFrom-Json
$chunks = @()
if ($payload -is [System.Array]) { $chunks = $payload } else { $chunks = @($payload) }

$rows = New-Object System.Collections.Generic.List[object]
foreach ($chunk in $chunks) {
  $chunkResults = Get-ObjectPropertyValue -Object $chunk -Name "results"
  if (-not $chunkResults) { continue }

  foreach ($row in @($chunkResults)) {
    $st = Get-ObjectPropertyValue -Object $row -Name "searchTermView"
    $campaign = Get-ObjectPropertyValue -Object $row -Name "campaign"
    $adGroup = Get-ObjectPropertyValue -Object $row -Name "adGroup"
    $metrics = Get-ObjectPropertyValue -Object $row -Name "metrics"

    $searchTerm = Get-ObjectPropertyValue -Object $st -Name "searchTerm"
    $status = Get-ObjectPropertyValue -Object $st -Name "status"
    $campaignName = Get-ObjectPropertyValue -Object $campaign -Name "name"
    $campaignId = Get-ObjectPropertyValue -Object $campaign -Name "id"
    $adGroupName = Get-ObjectPropertyValue -Object $adGroup -Name "name"
    $adGroupId = Get-ObjectPropertyValue -Object $adGroup -Name "id"
    $impressions = Get-ObjectPropertyValue -Object $metrics -Name "impressions"
    $clicks = Get-ObjectPropertyValue -Object $metrics -Name "clicks"
    $costMicros = Get-ObjectPropertyValue -Object $metrics -Name "costMicros"
    $conversions = Get-ObjectPropertyValue -Object $metrics -Name "conversions"

    $rows.Add([PSCustomObject]@{
      search_term = if ($null -eq $searchTerm) { "" } else { [string]$searchTerm }
      campaign = if ($null -eq $campaignName) { "" } else { [string]$campaignName }
      campaign_id = $campaignId
      ad_group = if ($null -eq $adGroupName) { "" } else { [string]$adGroupName }
      ad_group_id = $adGroupId
      impressions = if ($null -ne $impressions) { [int64]$impressions } else { 0 }
      clicks = if ($null -ne $clicks) { [int64]$clicks } else { 0 }
      cost_micros = if ($null -ne $costMicros) { [int64]$costMicros } else { 0 }
      conversions = if ($null -ne $conversions) { [double]$conversions } else { 0.0 }
      status = if ($null -eq $status) { "" } else { [string]$status }
    })
  }
}

$jsonRows = $rows | ConvertTo-Json -Depth 20 -Compress

if ($outputFile) {
  Set-Content -LiteralPath $outputFile -Value $jsonRows -Encoding UTF8
}

if (-not $quiet) {
  Write-Host ("Rows: {0}" -f $rows.Count)
  if ($rows.Count -gt 0) {
    Write-Host "| # | Search term | Campaign | Ad group | Impr | Clicks | Cost micros | Conv | Status |"
    Write-Host "|---|-------------|----------|----------|------|--------|-------------|------|--------|"
    $preview = [Math]::Min(50, $rows.Count)
    for ($idx = 0; $idx -lt $preview; $idx++) {
      $r = $rows[$idx]
      Write-Host ("| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} |" -f ($idx + 1), $r.search_term, $r.campaign, $r.ad_group, $r.impressions, $r.clicks, $r.cost_micros, $r.conversions, $r.status)
    }
    if ($rows.Count -gt 50) {
      Write-Host ("... and {0} more rows" -f ($rows.Count - 50))
    }
  }
}

Write-Output $jsonRows


