param(
  [string]$WorkflowJson = "$PSScriptRoot\legal-rag.json",
  [string]$WorkflowId = $null
)

$N8N_URL = $env:N8N_API_URL
$N8N_KEY = $env:N8N_API_KEY

if (-not $N8N_URL) { $N8N_URL = "http://localhost:5678" }
if (-not $N8N_KEY) { Write-Error "N8N_API_KEY not set"; exit 1 }

$json = Get-Content -LiteralPath $WorkflowJson -Raw | ConvertFrom-Json
$headers = @{ "X-N8N-API-KEY" = $N8N_KEY; "Content-Type" = "application/json" }

if ($WorkflowId) {
  Write-Host "Pushing to existing: $WorkflowId"
  $body = @{ name = $json.name; nodes = $json.nodes; connections = $json.connections; settings = $json.settings } | ConvertTo-Json -Depth 20 -Compress
  Invoke-RestMethod -Uri "$N8N_URL/api/v1/workflows/$WorkflowId" -Method Put -Headers $headers -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 1
} else {
  Write-Host "Creating: $($json.name)"
  $body = @{ name = $json.name; nodes = $json.nodes; connections = $json.connections; settings = @{ executionOrder = "v1" } } | ConvertTo-Json -Depth 20 -Compress
  $r = Invoke-RestMethod -Uri "$N8N_URL/api/v1/workflows" -Method Post -Headers $headers -Body $body -ContentType "application/json"
  Write-Host "Created: $($r.id)"
}
