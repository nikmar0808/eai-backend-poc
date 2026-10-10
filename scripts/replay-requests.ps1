# Replays every request file against the gateway and against the Python service directly,
# and prints the HTTP status each returned. Used as the safety net for refactoring.
# Prerequisite: the stack is running and API_SECURITY_TOKEN is set in this shell (see docs/comprehension/poc2.md).
param(
  [string]$JavaUrl   = 'http://localhost:8081/api/v1/ingest/bulk',
  [string]$PythonUrl = 'http://localhost:8082/api/v1/transform',
  [string]$Dir       = (Join-Path $PSScriptRoot '..\docs\comprehension\requests')
)
if (-not $env:API_SECURITY_TOKEN) { throw 'API_SECURITY_TOKEN is not set in this shell.' }
$rows = foreach ($f in Get-ChildItem -Path $Dir -Filter *.json | Sort-Object Name) {
  $java = curl.exe -s -o NUL -w '%{http_code}' -X POST $JavaUrl -H 'Content-Type: application/json' -d "@$($f.FullName)"
  $py   = curl.exe -s -o NUL -w '%{http_code}' -X POST $PythonUrl -H 'Content-Type: application/json' -H "X-EAI-TOKEN: $env:API_SECURITY_TOKEN" -d "@$($f.FullName)"
  [pscustomobject]@{ Request = $f.Name; Java = $java; Python = $py }
}
$rows | Format-Table -AutoSize
