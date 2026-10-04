$base = "http://localhost:8000"
$tmp = "D:\autoSage\.smoke_tmp"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$pass = 0; $fail = 0; $slow = 0

function Hit($method, $path, $token = $null, $bodyFile = $null) {
    $outFile = Join-Path $tmp "resp.txt"
    if (Test-Path $outFile) { Remove-Item $outFile -Force }
    $cmd = "curl.exe -s -m 60 -o `"$outFile`" -w `"%{http_code} %{time_total}`" -X $method `"$base$path`""
    if ($token) { $cmd += " -H `"Authorization: Bearer $token`"" }
    if ($bodyFile) { $cmd += " -H `"Content-Type: application/json`" -d `"`@$bodyFile`"" }
    $stdout = cmd /c $cmd 2>$null
    $parts = @($stdout -split " ", 2)
    $code = $parts[0]
    $time = if ($parts.Count -gt 1) { $parts[1] } else { "0" }
    $bodyOut = if (Test-Path $outFile) { Get-Content $outFile -Raw } else { "" }
    return @{ code = $code; time = $time; body = $bodyOut }
}

function Report($label, $res) {
    $code = $res.code; $time = $res.time
    $mark = "OK "
    if ($code -eq "000") { $mark = "ERR"; $script:fail++ }
    elseif ($code -ge "500") { $mark = "5XX"; $script:fail++ }
    else { $script:pass++ }
    if ([double]$time -gt 10) { $script:slow++ }
    "{0} [{1,3}] {2,7}s  {3}" -f $mark, $code, $time, $label
}

function BodyFile($name, $content) {
    $p = Join-Path $tmp $name
    Set-Content -Path $p -Value $content -NoNewline -Encoding utf8
    return $p
}

"=== AUTOSAGE BACKEND SMOKE $(Get-Date -Format 'HH:mm:ss') ==="

$r = Hit "GET" "/health"; Report "GET /health" $r
$r = Hit "GET" "/api/v1/health"; Report "GET /api/v1/health" $r

$devBody = BodyFile "dev.json" '{"email":"smoke@test.local","name":"Smoke"}'
$r = Hit "POST" "/api/v1/auth/dev-token" $null $devBody
Report "POST /api/v1/auth/dev-token" $r
$token = $null
if ($r.code -eq "201") {
    $m = [regex]::Match($r.body, '"access_token"\s*:\s*"([^"]+)"')
    if ($m.Success) { $token = $m.Groups[1].Value }
}
if (-not $token) { "FATAL: no token"; exit 1 }

$r = Hit "GET" "/api/v1/auth/me" $null; Report "GET /api/v1/auth/me (no auth -> expect 401)" $r
$r = Hit "GET" "/api/v1/auth/me" $token; Report "GET /api/v1/auth/me" $r
$r = Hit "GET" "/api/v1/auth/session" $token; Report "GET /api/v1/auth/session" $r

$r = Hit "GET" "/api/v1/workspaces" $token; Report "GET /api/v1/workspaces" $r
$wsId = $null
if ($r.code -eq "200") {
    $m = [regex]::Match($r.body, '"items"\s*:\s*\[\s*\{\s*"id"\s*:\s*"([^"]+)"')
    if ($m.Success) { $wsId = $m.Groups[1].Value }
}
$r = Hit "POST" "/api/v1/workspaces" $token (BodyFile "ws.json" '{"name":"Smoke WS ps"}')
Report "POST /api/v1/workspaces" $r
if (-not $wsId) {
    $m = [regex]::Match($r.body, '"id"\s*:\s*"([^"]+)"')
    if ($m.Success) { $wsId = $m.Groups[1].Value }
}

$r = Hit "GET" "/api/v1/experiments" $token; Report "GET /api/v1/experiments" $r

$expJson = '{"name":"Smoke Exp","description":"smoke","workspace_id":"' + $wsId + '","config":{"prompt":"test","dataset":"iris","task_type":"classification","target_column":"species","evaluation_metric":"f1","split_strategy":"random","imbalance_handling":"none","source":"smoke"},"max_retries":3}'
$r = Hit "POST" "/api/v1/experiments" $token (BodyFile "exp.json" $expJson)
Report "POST /api/v1/experiments" $r
$expId = $null
$m = [regex]::Match($r.body, '"id"\s*:\s*"([^"]+)"')
if ($m.Success -and ($r.code -eq "201" -or $r.code -eq "200")) { $expId = $m.Groups[1].Value }

if ($expId) {
    $r = Hit "GET" "/api/v1/experiments/$expId" $token; Report "GET /api/v1/experiments/{id}" $r
    $r = Hit "PATCH" "/api/v1/experiments/$expId" $token (BodyFile "patch.json" '{"name":"Smoke Renamed"}'); Report "PATCH /api/v1/experiments/{id}" $r
    $r = Hit "POST" "/api/v1/experiments/$expId/start" $token (BodyFile "empty.json" '{}'); Report "POST /api/v1/experiments/{id}/start" $r
    $r = Hit "POST" "/api/v1/experiments/$expId/cancel" $token (BodyFile "empty.json" '{}'); Report "POST /api/v1/experiments/{id}/cancel" $r
    $r = Hit "GET" "/api/v1/experiments/$expId/reproducibility" $token; Report "GET /api/v1/experiments/{id}/reproducibility" $r
    $r = Hit "DELETE" "/api/v1/experiments/$expId" $token; Report "DELETE /api/v1/experiments/{id}" $r
} else { "SKIP experiment subtests (no id)" }

$r = Hit "GET" "/api/v1/projects" $token; Report "GET /api/v1/projects" $r
$r = Hit "POST" "/api/v1/projects" $token (BodyFile "proj.json" '{"name":"Smoke Project","description":"smoke"}')
Report "POST /api/v1/projects" $r
$projId = $null
$m = [regex]::Match($r.body, '"id"\s*:\s*"([^"]+)"')
if ($m.Success -and ($r.code -eq "201" -or $r.code -eq "200")) { $projId = $m.Groups[1].Value }
if ($projId) {
    $r = Hit "GET" "/api/v1/projects/$projId" $token; Report "GET /api/v1/projects/{id}" $r
    $r = Hit "GET" "/api/v1/projects/$projId/datasets" $token; Report "GET /api/v1/projects/{id}/datasets" $r
    $r = Hit "GET" "/api/v1/projects/$projId/runs/" $token; Report "GET /api/v1/projects/{id}/runs" $r
}

$r = Hit "GET" "/api/v1/runs/00000000-0000-0000-0000-000000000000/evidence" $token; Report "GET /api/v1/runs/{id}/evidence (fake id)" $r
$r = Hit "GET" "/api/v1/memory/search?q=test" $token; Report "GET /api/v1/memory/search" $r
$r = Hit "GET" "/api/v1/verification/sources" $token; Report "GET /api/v1/verification/sources" $r
$r = Hit "GET" "/api/v1/verification/evidence/search?q=test" $token; Report "GET /api/v1/verification/evidence/search" $r
$r = Hit "GET" "/api/v1/verification/decision?experiment_id=00000000-0000-0000-0000-000000000000" $token; Report "GET /api/v1/verification/decision (fake id)" $r
$r = Hit "GET" "/api/v1/verification/experiment?experiment_id=00000000-0000-0000-0000-000000000000" $token; Report "GET /api/v1/verification/experiment (fake id)" $r
$r = Hit "GET" "/api/v1/storage/files" $token; Report "GET /api/v1/storage/files" $r
$r = Hit "GET" "/api/v1/storage/stats" $token; Report "GET /api/v1/storage/stats" $r
$r = Hit "GET" "/api/v1/storage/files/00000000-0000-0000-0000-000000000000" $token; Report "GET /api/v1/storage/files/{id} (fake id)" $r
$r = Hit "GET" "/api/v1/reproducibility" $token; Report "GET /api/v1/reproducibility" $r
$r = Hit "GET" "/api/v1/reproducibility/00000000-0000-0000-0000-000000000000" $token; Report "GET /api/v1/reproducibility/{id} (fake id)" $r

""
"=== SUMMARY: pass=$pass fail=$fail slow(>10s)=$slow ==="
