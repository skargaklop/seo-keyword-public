[CmdletBinding(PositionalBinding = $false)]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ScriptArguments)

if ($null -eq $ScriptArguments) {
  $ScriptArguments = @()
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "top_requests.ps1 is deprecated. Use keyword_ideas.ps1."
$forwardArgs = @($ScriptArguments | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
& (Join-Path $scriptDir "keyword_ideas.ps1") @forwardArgs
if ($?) { exit 0 } else { exit 1 }
