<#
.SYNOPSIS  Fetch a client-credentials token from the local Keycloak, and optionally decode it.
.EXAMPLE   .\scripts\get-token.ps1 -Client ingest-client -Decode
#>
param(
    # ValidateSet makes PowerShell refuse any other value, so a typo cannot silently ask for a nonexistent client.
    [ValidateSet('ingest-client', 'readonly-client', 'outsider-client')]
    [string]$Client = 'ingest-client',
    # 127.0.0.1, not localhost: the address to CALL (Stage 4, 4.5.2). The token's issuer is decided by Keycloak's
    # KC_HOSTNAME and still reads http://localhost:8180/realms/eai.
    [string]$KeycloakUrl = 'http://127.0.0.1:8180',
    [switch]$Decode
)
$ErrorActionPreference = 'Stop'    # a failed request stops the script instead of printing and continuing

if (-not $env:KEYCLOAK_CLIENT_SECRET) {
    throw 'KEYCLOAK_CLIENT_SECRET is not set in this shell. Run the .env loader line of Stage 5, section 5.2, in this window first.'
}

# POST with a hashtable body is sent as a form (application/x-www-form-urlencoded), which is what the token endpoint
# expects. The reply is JSON; Invoke-RestMethod converts it to an object.
$response = Invoke-RestMethod -Method Post -Uri "$KeycloakUrl/realms/eai/protocol/openid-connect/token" -Body @{
    grant_type    = 'client_credentials'
    client_id     = $Client
    client_secret = $env:KEYCLOAK_CLIENT_SECRET
}

# A JWT part is base64url: '-' and '_' replace '+' and '/', and the trailing '=' padding is dropped. Undo both.
function ConvertFrom-Base64Url([string]$Text) {
    $padded = $Text.Replace('-', '+').Replace('_', '/')
    switch ($padded.Length % 4) { 2 { $padded += '==' } 3 { $padded += '=' } }
    [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($padded))
}

if ($Decode) {
    $parts = $response.access_token.Split('.')                    # header . payload . signature
    $header  = ConvertFrom-Base64Url $parts[0] | ConvertFrom-Json
    $payload = ConvertFrom-Base64Url $parts[1] | ConvertFrom-Json
    "CLIENT   $Client"
    "HEADER   " + ($header | ConvertTo-Json -Compress)
    "PAYLOAD  " + ($payload | ConvertTo-Json -Compress)
    "EXPIRES  " + [DateTimeOffset]::FromUnixTimeSeconds($payload.exp).LocalDateTime + " (local time)"
    "LIFETIME " + ($payload.exp - $payload.iat) + " seconds"
    "(the signature is not decoded: it is binary, and only the gateway's key can check it)"
} else {
    $response.access_token
}
