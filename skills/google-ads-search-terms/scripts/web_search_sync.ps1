[CmdletBinding(PositionalBinding = $false)]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ScriptArguments)

if ($null -eq $ScriptArguments) {
  $ScriptArguments = @()
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($ScriptArguments.Count -gt 0 -and ($ScriptArguments[0] -eq '--help' -or $ScriptArguments[0] -eq '-h')) {
@"
web_search_sync.ps1 is deprecated.
Delegates to search_terms_sync.ps1.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts/web_search_sync.ps1 [options]

See:
  powershell -ExecutionPolicy Bypass -File scripts/search_terms_sync.ps1 --help
"@ | Write-Host
  exit 0
}
Write-Host "web_search_sync.ps1 is deprecated. Delegating to search_terms_sync.ps1."
$forwardArgs = @($ScriptArguments | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
& (Join-Path $scriptDir "search_terms_sync.ps1") @forwardArgs
if ($?) { exit 0 } else { exit 1 }
