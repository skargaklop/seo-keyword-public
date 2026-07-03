[CmdletBinding(PositionalBinding = $false)]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ScriptArguments)

if ($null -eq $ScriptArguments) {
  $ScriptArguments = @()
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$forwardArgs = @($ScriptArguments | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
& (Join-Path $scriptDir "geo_lookup.ps1") @forwardArgs
if ($?) { exit 0 } else { exit 1 }
