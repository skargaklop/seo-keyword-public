Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Script:GoogleAdsScriptDir = $PSScriptRoot
$Script:GoogleAdsSkillDir = Split-Path -Parent $Script:GoogleAdsScriptDir
$Script:GoogleAdsConfigFile = Join-Path $Script:GoogleAdsSkillDir "config/.env"
$Script:GoogleAdsCacheDir = Join-Path $Script:GoogleAdsSkillDir "cache"
$Script:GoogleAdsTokenCacheFile = Join-Path $Script:GoogleAdsCacheDir "google_ads_token.json"
$Script:GoogleAdsConfig = $null

function Ensure-GoogleAdsCacheDirs {
  if (-not (Test-Path -LiteralPath $Script:GoogleAdsCacheDir -PathType Container)) {
    New-Item -ItemType Directory -Path $Script:GoogleAdsCacheDir | Out-Null
  }

  $resultsDir = Join-Path $Script:GoogleAdsCacheDir "results"
  $opsDir = Join-Path $Script:GoogleAdsCacheDir "ops"

  if (-not (Test-Path -LiteralPath $resultsDir -PathType Container)) {
    New-Item -ItemType Directory -Path $resultsDir | Out-Null
  }
  if (-not (Test-Path -LiteralPath $opsDir -PathType Container)) {
    New-Item -ItemType Directory -Path $opsDir | Out-Null
  }
}

function Normalize-GoogleAdsCustomerId {
  param([string]$Raw)

  if ($null -eq $Raw) {
    return ""
  }

  return (($Raw -replace "[\s-]", "").Trim())
}

function Get-GoogleAdsApiVersion {
  if ($Script:GoogleAdsConfig -and $Script:GoogleAdsConfig.ContainsKey("GOOGLE_ADS_API_VERSION") -and $Script:GoogleAdsConfig.GOOGLE_ADS_API_VERSION) {
    return $Script:GoogleAdsConfig.GOOGLE_ADS_API_VERSION
  }
  return "v22"
}

function Get-GoogleAdsApiBaseUrl {
  return "https://googleads.googleapis.com/$(Get-GoogleAdsApiVersion)"
}

function Read-DotEnvFile {
  param([string]$Path)

  $data = @{}
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $data
  }

  foreach ($line in (Get-Content -LiteralPath $Path -Encoding UTF8)) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith("#")) {
      continue
    }

    $match = [regex]::Match($trimmed, "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")
    if (-not $match.Success) {
      continue
    }

    $name = $match.Groups[1].Value
    $value = $match.Groups[2].Value

    if ($value.Length -ge 2) {
      if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
    }

    $data[$name] = $value
  }

  return $data
}

function Load-GoogleAdsConfig {
  $fromFile = Read-DotEnvFile -Path $Script:GoogleAdsConfigFile

  $required = @(
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CUSTOMER_ID"
  )

  $cfg = @{}
  foreach ($name in $required + @("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "GOOGLE_ADS_API_VERSION")) {
    $envValue = [Environment]::GetEnvironmentVariable($name, "Process")
    if ($envValue) {
      $cfg[$name] = $envValue
    }
    elseif ($fromFile.ContainsKey($name)) {
      $cfg[$name] = $fromFile[$name]
    }
    else {
      $cfg[$name] = ""
    }
  }

  $missing = @()
  foreach ($name in $required) {
    if (-not $cfg[$name]) {
      $missing += $name
    }
  }

  if ($missing.Count -gt 0) {
    foreach ($name in $missing) {
      Write-Error "Error: $name is not set."
    }
    throw "Fill $($Script:GoogleAdsConfigFile) (see config/README.md)."
  }

  $cfg.GOOGLE_ADS_CUSTOMER_ID = Normalize-GoogleAdsCustomerId -Raw $cfg.GOOGLE_ADS_CUSTOMER_ID
  if ($cfg.GOOGLE_ADS_LOGIN_CUSTOMER_ID) {
    $cfg.GOOGLE_ADS_LOGIN_CUSTOMER_ID = Normalize-GoogleAdsCustomerId -Raw $cfg.GOOGLE_ADS_LOGIN_CUSTOMER_ID
  }

  if (-not $cfg.GOOGLE_ADS_API_VERSION) {
    $cfg.GOOGLE_ADS_API_VERSION = "v22"
  }

  $Script:GoogleAdsConfig = $cfg
  return $cfg
}

function Ensure-GoogleAdsConfigLoaded {
  if (-not $Script:GoogleAdsConfig) {
    [void](Load-GoogleAdsConfig)
  }
}

function Read-HttpErrorBody {
  param([Parameter(Mandatory = $true)]$Exception)

  $response = $null

  $innerException = $null
  if ($Exception -and $Exception.PSObject.Properties['Exception']) {
    $innerException = $Exception.Exception
  }

  if ($innerException -and $innerException.PSObject.Properties['Response']) {
    $response = $innerException.Response
  }
  elseif ($Exception -and $Exception.PSObject.Properties['Response']) {
    $response = $Exception.Response
  }

  if (-not $response) {
    return $Exception.ToString()
  }

  $stream = $response.GetResponseStream()
  if (-not $stream) {
    return $null
  }

  $reader = New-Object System.IO.StreamReader($stream)
  try {
    return $reader.ReadToEnd()
  }
  finally {
    $reader.Dispose()
    $stream.Dispose()
  }
}

function Refresh-GoogleAdsAccessToken {
  Ensure-GoogleAdsConfigLoaded

  $form = @{
    client_id     = $Script:GoogleAdsConfig.GOOGLE_ADS_CLIENT_ID
    client_secret = $Script:GoogleAdsConfig.GOOGLE_ADS_CLIENT_SECRET
    refresh_token = $Script:GoogleAdsConfig.GOOGLE_ADS_REFRESH_TOKEN
    grant_type    = "refresh_token"
  }

  try {
    $resp = Invoke-RestMethod -Method Post -Uri "https://oauth2.googleapis.com/token" -ContentType "application/x-www-form-urlencoded" -Body $form
  }
  catch {
    $body = Read-HttpErrorBody -Exception $_
    if ($body) {
      throw "Error: OAuth refresh failed: $body"
    }
    throw
  }

  if (-not $resp.access_token) {
    $msg = $resp.error_description
    if (-not $msg) {
      $msg = $resp.error
    }
    if (-not $msg) {
      $msg = "access_token missing"
    }
    throw "Error: OAuth refresh failed: $msg"
  }

  $expiresIn = 3600
  if ($resp.expires_in) {
    $expiresIn = [int]$resp.expires_in
  }

  $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  $expiresAt = $now + $expiresIn - 60

  Ensure-GoogleAdsCacheDirs

  $payload = [ordered]@{
    access_token = [string]$resp.access_token
    expires_at   = [int64]$expiresAt
  }

  $tmpFile = "$($Script:GoogleAdsTokenCacheFile).tmp"
  $json = $payload | ConvertTo-Json -Compress
  Set-Content -LiteralPath $tmpFile -Value $json -Encoding UTF8
  Move-Item -LiteralPath $tmpFile -Destination $Script:GoogleAdsTokenCacheFile -Force

  return [string]$resp.access_token
}

function Get-GoogleAdsAccessToken {
  Ensure-GoogleAdsCacheDirs

  if (Test-Path -LiteralPath $Script:GoogleAdsTokenCacheFile -PathType Leaf) {
    try {
      $cached = Get-Content -LiteralPath $Script:GoogleAdsTokenCacheFile -Raw -Encoding UTF8 | ConvertFrom-Json
      $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
      if ($cached.expires_at -and [int64]$cached.expires_at -gt ($now + 30) -and $cached.access_token) {
        return [string]$cached.access_token
      }
    }
    catch {
      # ignore broken cache
    }
  }

  return Refresh-GoogleAdsAccessToken
}

function Invoke-GoogleAdsRequest {
  param(
    [Parameter(Mandatory = $true)][ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE")][string]$Method,
    [Parameter(Mandatory = $true)][string]$Endpoint,
    [string]$BodyJson = "{}"
  )

  Ensure-GoogleAdsConfigLoaded

  $token = Get-GoogleAdsAccessToken
  $headers = @{
    Authorization     = "Bearer $token"
    "developer-token" = $Script:GoogleAdsConfig.GOOGLE_ADS_DEVELOPER_TOKEN
  }

  if ($Script:GoogleAdsConfig.GOOGLE_ADS_LOGIN_CUSTOMER_ID) {
    $headers["login-customer-id"] = $Script:GoogleAdsConfig.GOOGLE_ADS_LOGIN_CUSTOMER_ID
  }

  $url = "$(Get-GoogleAdsApiBaseUrl)/$Endpoint"

  try {
    $requestParams = @{
      Method  = $Method
      Uri     = $url
      Headers = $headers
    }

    if ($Method -in @("POST", "PUT", "PATCH", "DELETE")) {
      $requestParams["ContentType"] = "application/json"
      $requestParams["Body"] = $BodyJson
    }

    $resp = Invoke-RestMethod @requestParams
    return ($resp | ConvertTo-Json -Depth 100 -Compress)
  }
  catch {
    $body = Read-HttpErrorBody -Exception $_
    if ($body) {
      return [string]$body
    }
    throw
  }
}

function Get-ObjectPropertyValue {
  param(
    [Parameter(Mandatory = $true)]$Object,
    [Parameter(Mandatory = $true)][string]$Name
  )

  if ($null -eq $Object) {
    return $null
  }

  if ($Object.PSObject -and $Object.PSObject.Properties[$Name]) {
    return $Object.$Name
  }

  return $null
}

function Test-GoogleAdsApiError {
  param([Parameter(Mandatory = $true)][string]$Payload)

  if ([string]::IsNullOrWhiteSpace($Payload)) {
    return $true
  }

  try {
    $obj = $Payload | ConvertFrom-Json
  }
  catch {
    return $true
  }

  if ($obj -is [System.Array]) {
    return $false
  }

  $errorObj = Get-ObjectPropertyValue -Object $obj -Name "error"
  return ($null -ne $errorObj)
}

function Write-GoogleAdsApiError {
  param([Parameter(Mandatory = $true)][string]$Payload)

  try {
    $obj = $Payload | ConvertFrom-Json
  }
  catch {
    Write-Host $Payload
    return
  }

  $errorObj = Get-ObjectPropertyValue -Object $obj -Name "error"
  if ($obj -is [System.Array] -or $null -eq $errorObj) {
    Write-Host $Payload
    return
  }

  $code = Get-ObjectPropertyValue -Object $errorObj -Name "code"
  if ($null -eq $code -or "$code" -eq "") { $code = "?" }
  $status = Get-ObjectPropertyValue -Object $errorObj -Name "status"
  if ($null -eq $status -or "$status" -eq "") { $status = "UNKNOWN" }
  $message = Get-ObjectPropertyValue -Object $errorObj -Name "message"
  if ($null -eq $message) { $message = "" }

  Write-Host "Google Ads API error: $code $status`: $message"

  $details = Get-ObjectPropertyValue -Object $errorObj -Name "details"
  if ($details) {
    foreach ($detail in $details) {
      $detailErrors = Get-ObjectPropertyValue -Object $detail -Name "errors"
      if ($detailErrors) {
        Write-Host ($detailErrors | ConvertTo-Json -Compress)
      }
      else {
        $detailType = Get-ObjectPropertyValue -Object $detail -Name "@type"
        if ($detailType) {
          Write-Host $detailType
        }
      }
    }
  }
}





