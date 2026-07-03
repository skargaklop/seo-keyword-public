[CmdletBinding(PositionalBinding = $false)]
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ScriptArguments)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($null -eq $ScriptArguments) {
  $ScriptArguments = @()
}

function Show-Usage {
@"
Usage: search_region.ps1 --name "Moscow"

Deprecated wrapper:
  Delegates to geo_lookup.ps1 --query "<name>"
"@ | Write-Host
}

$name = ""
for ($i = 0; $i -lt $ScriptArguments.Count; $i++) {
  switch ($ScriptArguments[$i]) {
    '--name' { if ($i + 1 -ge $ScriptArguments.Count) { throw 'Missing value for --name' }; $name = $ScriptArguments[++$i] }
    '-n' { if ($i + 1 -ge $ScriptArguments.Count) { throw 'Missing value for -n' }; $name = $ScriptArguments[++$i] }
    '--help' { Show-Usage; exit 0 }
    '-h' { Show-Usage; exit 0 }
    default { Write-Error "Unknown option: $($ScriptArguments[$i])"; exit 1 }
  }
}

if (-not $name) {
  Show-Usage
  exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "search_region.ps1 is deprecated. Delegating to geo_lookup.ps1."
& (Join-Path $scriptDir 'geo_lookup.ps1') --query $name
if ($?) { exit 0 } else { exit 1 }

