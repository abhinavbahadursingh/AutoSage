# E2E Start flow
Write-Host '=== 1. Get dev token ==='
$authJson = curl.exe -s -m 30 -X POST "http://127.0.0.1:8000/api/v1/auth/dev-token" -H "Content-Type: application/json" -d '{}'
Write-Host "dev-token: $authJson"
$token = ($authJson | ConvertFrom-Json).access_token
if (-not $token) { Write-Host "NO TOKEN"; exit 1 }
Write-Host "token acquired (${$token.Length} chars)"

Write-Host ''
Write-Host '=== 2. Get workspaces ==='
$ws = curl.exe -s -m 15 -H "Authorization: Bearer $token" "http://127.0.0.1:8000/api/v1/workspaces"
Write-Host "workspaces: $ws"
$wsObj = $ws | ConvertFrom-Json
$wsId = $wsObj[0].id
Write-Host "workspace: $wsId"

Write-Host ''
Write-Host '=== 3. Create experiment ==='
$expBody = @{
  name = "E2E Test"
  description = "from curl"
  workspace_id = $wsId
  config = @{
    prompt = "test"
    dataset = "iris"
    task_type = "classification"
    target_column = "species"
    evaluation_metric = "f1"
    split_strategy = "random"
    imbalance_handling = "none"
    source = "e2e"
  }
  max_retries = 3
} | ConvertTo-Json -Depth 5 -Compress
$expBody | Out-File -Encoding utf8 D:\autoSage\create_exp.json
$cmdCreate = 'curl.exe -s -m 30 -X POST "http://127.0.0.1:8000/api/v1/experiments" -H "Authorization: Bearer ' + $token + '" -H "Content-Type: application/json" -d @"D:\autoSage\create_exp.json"'
$exp = Invoke-Expression $cmdCreate
Write-Host "create: $exp"
$expObj = $exp | ConvertFrom-Json
$expId = $expObj.id
Write-Host "experiment: $expId status=$($expObj.status)"

Write-Host ''
Write-Host '=== 4. Start experiment ==='
'{}' | Out-File -Encoding utf8 D:\autoSage\empty.json
$cmdStart = 'curl.exe -s -m 60 -X POST "http://127.0.0.1:8000/api/v1/experiments/' + $expId + '/start" -H "Authorization: Bearer ' + $token + '" -H "Content-Type: application/json" -d @"D:\autoSage\empty.json"'
$startJson = Invoke-Expression $cmdStart
Write-Host "start: $startJson"
$startObj = $startJson | ConvertFrom-Json
Write-Host "started status=$($startObj.status)"

Write-Host ''
Write-Host '=== 5. Poll for status ==='
Start-Sleep -Seconds 3
$status = curl.exe -s -m 15 -H "Authorization: Bearer $token" "http://127.0.0.1:8000/api/v1/experiments/$expId"
Write-Host "status: $status"