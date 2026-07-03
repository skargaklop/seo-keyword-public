[CmdletBinding(PositionalBinding = $false)]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ScriptArguments)

if ($null -eq $ScriptArguments) {
  $ScriptArguments = @()
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "iam_token_get.ps1 is removed. Use auth_check.ps1 (OAuth refresh token flow)."

$forwardArgs = @($ScriptArguments | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
& (Join-Path $scriptDir "auth_check.ps1") @forwardArgs

if ($?) { exit 0 } else { exit 1 }
