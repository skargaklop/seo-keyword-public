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
Usage: search_terms_batch.ps1 [options]

Options:
  --date-from           Start date YYYY-MM-DD (required unless --resume)
  --date-to             End date YYYY-MM-DD (required unless --resume)
  --step-days           Chunk size in days (default: 7)
  --campaign-ids        Comma-separated campaign IDs (optional)
  --customer-id, -c     Override GOOGLE_ADS_CUSTOMER_ID
  --resume              Resume pending/error operations from cache/ops
  --force               Re-run done operations
  --limit               Limit per chunk query (default: 5000)
  --help, -h            Show help
"@ | Write-Host
}

function Get-Md5Hex {
  param([Parameter(Mandatory = $true)][string]$Input)

  $bytes = [System.Text.Encoding]::UTF8.GetBytes($Input)
  $md5 = [System.Security.Cryptography.MD5]::Create()
  try {
    $hash = $md5.ComputeHash($bytes)
  } finally {
    $md5.Dispose()
  }

  return (($hash | ForEach-Object { $_.ToString("x2") }) -join "")
}

function Read-JsonFile {
  param([Parameter(Mandatory = $true)][string]$Path)
  return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-JsonFile {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)]$Object
  )

  $json = $Object | ConvertTo-Json -Depth 100
  Set-Content -LiteralPath $Path -Value $json -Encoding UTF8
}

function Process-Operation {
  param(
    [Parameter(Mandatory = $true)][string]$OperationPath,
    [Parameter(Mandatory = $true)][string]$SyncScript,
    [Parameter(Mandatory = $true)][int]$Limit,
    [Parameter(Mandatory = $true)][string]$CustomerId
  )

  $op = Read-JsonFile -Path $OperationPath

  $cmdArgs = @(
    "--date-from", [string]$op.date_from,
    "--date-to", [string]$op.date_to,
    "--limit", [string]$Limit,
    "--customer-id", $CustomerId,
    "--quiet"
  )

  if ($op.campaign_id) {
    $cmdArgs += @("--campaign-ids", [string]$op.campaign_id)
  }

  $output = & $SyncScript @cmdArgs 2>$null
  $exitCode = if ($?) { 0 } else { 1 }
  $raw = if ($output -is [System.Array]) { ($output -join "`n") } else { [string]$output }

  if ($exitCode -eq 0) {
    Set-Content -LiteralPath ([string]$op.result_file) -Value $raw -Encoding UTF8
    $op.status = "done"
    $op.updated_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $op.error = $null
    Write-JsonFile -Path $OperationPath -Object $op
    Write-Host ("DONE: {0}" -f [System.IO.Path]::GetFileName($OperationPath))
  } else {
    $op.status = "error"
    $op.updated_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $op.error = "search_terms_sync failed"
    Write-JsonFile -Path $OperationPath -Object $op
    Write-Host ("ERROR: {0}" -f [System.IO.Path]::GetFileName($OperationPath))
  }
}

$dateFrom = ""
$dateTo = ""
$stepDays = 7
$campaignIds = ""
$customerId = ""
$resumeMode = $false
$forceMode = $false
$limit = 5000

for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
  $arg = $ScriptArguments[$i]
  switch ($arg) {
    "--date-from" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --date-from" }; $dateFrom = $ScriptArguments[++$i] }
    "--date-to" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --date-to" }; $dateTo = $ScriptArguments[++$i] }
    "--step-days" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --step-days" }; $stepDays = [int]$ScriptArguments[++$i] }
    "--campaign-ids" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --campaign-ids" }; $campaignIds = $ScriptArguments[++$i] }
    "--customer-id" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --customer-id" }; $customerId = $ScriptArguments[++$i] }
    "-c" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for -c" }; $customerId = $ScriptArguments[++$i] }
    "--resume" { $resumeMode = $true }
    "--force" { $forceMode = $true }
    "--limit" { if ($i + 1 -ge $ScriptArguments.Count) { throw "Missing value for --limit" }; $limit = [int]$ScriptArguments[++$i] }
    "--help" { Show-Usage; exit 0 }
    "-h" { Show-Usage; exit 0 }
    default { Write-Error "Unknown option: $arg"; Show-Usage; exit 1 }
  }
}

[void](Load-GoogleAdsConfig)
Ensure-GoogleAdsCacheDirs

if (-not $customerId) {
  $customerId = $Script:GoogleAdsConfig.GOOGLE_ADS_CUSTOMER_ID
} else {
  $customerId = Normalize-GoogleAdsCustomerId -Raw $customerId
}

$opsDir = Join-Path $scriptDir "../cache/ops"
$resultsDir = Join-Path $scriptDir "../cache/results"
if (-not (Test-Path -LiteralPath $opsDir -PathType Container)) { New-Item -ItemType Directory -Path $opsDir | Out-Null }
if (-not (Test-Path -LiteralPath $resultsDir -PathType Container)) { New-Item -ItemType Directory -Path $resultsDir | Out-Null }

$syncScript = Join-Path $scriptDir "search_terms_sync.ps1"
$limit = [Math]::Max(1, $limit)

if ($resumeMode) {
  $files = @(Get-ChildItem -LiteralPath $opsDir -Filter *.json -File)
  if ($files.Count -eq 0) {
    Write-Host "No cached operations in cache/ops."
    exit 0
  }

  foreach ($file in $files) {
    $op = Read-JsonFile -Path $file.FullName
    $status = if ($op.status) { [string]$op.status } else { "pending" }
    if ($status -ne "done" -or $forceMode) {
      Process-Operation -OperationPath $file.FullName -SyncScript $syncScript -Limit $limit -CustomerId $customerId
    }
  }
} else {
  if (-not $dateFrom -or -not $dateTo) {
    Write-Error "Error: --date-from and --date-to are required unless --resume."
    exit 1
  }

  $start = [DateTime]::ParseExact($dateFrom, "yyyy-MM-dd", [System.Globalization.CultureInfo]::InvariantCulture)
  $end = [DateTime]::ParseExact($dateTo, "yyyy-MM-dd", [System.Globalization.CultureInfo]::InvariantCulture)
  if ($end -lt $start) {
    throw "date-to must be >= date-from"
  }

  $stepDays = [Math]::Max(1, $stepDays)
  $campaignList = @($campaignIds.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  if ($campaignList.Count -eq 0) {
    $campaignList = @("")
  }

  $current = $start
  while ($current -le $end) {
    $chunkEnd = $current.AddDays($stepDays - 1)
    if ($chunkEnd -gt $end) {
      $chunkEnd = $end
    }

    foreach ($cid in $campaignList) {
      $fromStr = $current.ToString("yyyy-MM-dd")
      $toStr = $chunkEnd.ToString("yyyy-MM-dd")
      $keySrc = "$fromStr|$toStr|$cid"
      $key = (Get-Md5Hex -Input $keySrc).Substring(0, 16)

      $opPath = Join-Path $opsDir "$key.json"
      $resultPath = Join-Path $resultsDir "$key.json"

      $writeOp = $true
      if (Test-Path -LiteralPath $opPath -PathType Leaf) {
        $existing = Read-JsonFile -Path $opPath
        if ($existing.status -eq "done" -and -not $forceMode) {
          $writeOp = $false
        }
      }

      if ($writeOp) {
        $payload = [ordered]@{
          id = $key
          status = "pending"
          date_from = $fromStr
          date_to = $toStr
          campaign_id = $cid
          result_file = $resultPath
          updated_at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
          error = $null
        }
        Write-JsonFile -Path $opPath -Object $payload
      }
    }

    $current = $chunkEnd.AddDays(1)
  }

  $files = @(Get-ChildItem -LiteralPath $opsDir -Filter *.json -File)
  foreach ($file in $files) {
    $op = Read-JsonFile -Path $file.FullName
    $status = if ($op.status) { [string]$op.status } else { "pending" }
    if ($status -eq "pending" -or $status -eq "error" -or $forceMode) {
      Process-Operation -OperationPath $file.FullName -SyncScript $syncScript -Limit $limit -CustomerId $customerId
    }
  }
}

$files = @(Get-ChildItem -LiteralPath $opsDir -Filter *.json -File)
$stats = @{ done = 0; pending = 0; error = 0 }
foreach ($file in $files) {
  $op = Read-JsonFile -Path $file.FullName
  $status = if ($op.status) { [string]$op.status } else { "pending" }
  if (-not $stats.ContainsKey($status)) {
    $stats[$status] = 0
  }
  $stats[$status]++
}

Write-Host ("Summary: done={0} pending={1} error={2} total={3}" -f $stats.done, $stats.pending, $stats.error, $files.Count)


