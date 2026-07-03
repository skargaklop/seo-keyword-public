[CmdletBinding(PositionalBinding = $false)]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ScriptArguments)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($null -eq $ScriptArguments) {
  $ScriptArguments = @()
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$phrase = ""
$other = New-Object System.Collections.Generic.List[string]

for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
  switch ($ScriptArguments[$i]) {
    '--phrase' { if ($i + 1 -ge $ScriptArguments.Count) { throw 'Missing value for --phrase' }; $phrase = $ScriptArguments[++$i] }
    '-p' { if ($i + 1 -ge $ScriptArguments.Count) { throw 'Missing value for -p' }; $phrase = $ScriptArguments[++$i] }
    default { $other.Add($ScriptArguments[$i]) }
  }
}

if (-not $phrase) {
  Write-Host 'dynamics.ps1 is deprecated. Use historical_metrics.ps1 --keywords "k1,k2".'
  & (Join-Path $scriptDir 'historical_metrics.ps1') @($other.ToArray())
  if ($?) { exit 0 } else { exit 1 }
}

Write-Host 'dynamics.ps1 is deprecated. Mapping --phrase to --keywords.'
$args = @('--keywords', $phrase) + $other.ToArray()
& (Join-Path $scriptDir 'historical_metrics.ps1') @args
if ($?) { exit 0 } else { exit 1 }

