param(
  [Parameter(Mandatory=$true)]
  [string]$WorkflowId,
  [string]$OutputFile = "$PSScriptRoot\legal-rag.json"
)

$N8N_URL = $env:N8N_API_URL
$N8N_KEY = $env:N8N_API_KEY

if (-not $N8N_URL) { $N8N_URL = "http://localhost:5678" }
if (-not $N8N_KEY) { Write-Error "N8N_API_KEY not set"; exit 1 }

$headers = @{ "X-N8N-API-KEY" = $N8N_KEY }

Write-Host "Fetching workflow: $WorkflowId"
$wf = Invoke-RestMethod -Uri "$N8N_URL/api/v1/workflows/$WorkflowId" -Headers $headers

$wf.meta = $null
$wf.id = $null
$wf.versionId = $null
$wf.createdAt = $null
$wf.updatedAt = $null
$wf.shared = $null

$wf | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $OutputFile -Encoding UTF8
Write-Host "Saved to $OutputFile"
