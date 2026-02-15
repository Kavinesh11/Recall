# Recall MCP Server - API Testing Script (PowerShell)
# Run this after starting the server with: docker-compose up -d

$BaseUrl = "http://localhost:8000"

# Load local .env (if present) into environment for the demo (safe, not committed)
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        $_ = $_.Trim()
        if ($_.Length -eq 0 -or $_.StartsWith('#')) { return }
        $pair = $_ -split '='
        if ($pair.Length -ge 2) {
            $name = $pair[0].Trim()
            $value = ($pair[1..($pair.Length - 1)] -join '=').Trim()
            $env:$name = $value
        }
    }
}

# MODEL_PROVIDER can be set in .env or overridden here:
# $env:MODEL_PROVIDER = "gemini"


Write-Host "================================" -ForegroundColor Cyan
Write-Host "Recall MCP Server - API Tests" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health Check
Write-Host "Test 1: Health Check" -ForegroundColor Yellow
Write-Host "--------------------" -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
$response | ConvertTo-Json
Write-Host ""

# Test 2: List Tools
Write-Host "Test 2: List Available Tools" -ForegroundColor Yellow
Write-Host "-----------------------------" -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "$BaseUrl/mcp/tools" -Method Get
$response | ConvertTo-Json
Write-Host ""

# Test 3: Get Root Info
Write-Host "Test 3: Server Info" -ForegroundColor Yellow
Write-Host "-------------------" -ForegroundColor Yellow
$response = Invoke-RestMethod -Uri "$BaseUrl/" -Method Get
$response | ConvertTo-Json
Write-Host ""

# Test 4: Valid Query Request
Write-Host "Test 4: Valid Query Request" -ForegroundColor Yellow
Write-Host "---------------------------" -ForegroundColor Yellow
try {
    $body = @{
        question = "Who won the most F1 World Championships?"
        run_id = "test-001"
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri "$BaseUrl/mcp/tools/ask_data_agent" `
        -Method Post `
        -ContentType "application/json" `
        -Headers @{"X-Archestra-Agent-Id"="test-agent"} `
        -Body $body
    
    Write-Host "✓ SUCCESS" -ForegroundColor Green
    $response | ConvertTo-Json
} catch {
    Write-Host "Note: Database may not be loaded yet" -ForegroundColor Yellow
    Write-Host $_.Exception.Message
}
Write-Host ""

# Test 5: Empty Question (Should Fail)
Write-Host "Test 5: Empty Question (Validation Error)" -ForegroundColor Yellow
Write-Host "-----------------------------------------" -ForegroundColor Yellow
try {
    $body = @{question = ""} | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BaseUrl/mcp/tools/ask_data_agent" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
    
    Write-Host "✗ FAILED - Should have rejected empty question" -ForegroundColor Red
} catch {
    Write-Host "✓ PASSED - Empty question rejected:" -ForegroundColor Green
    $_.Exception.Response
}
Write-Host ""

# Test 6: Missing Question (Should Fail)
Write-Host "Test 6: Missing Question Field (Validation Error)" -ForegroundColor Yellow
Write-Host "--------------------------------------------------" -ForegroundColor Yellow
try {
    $body = @{} | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BaseUrl/mcp/tools/ask_data_agent" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
    
    Write-Host "✗ FAILED - Should have rejected missing field" -ForegroundColor Red
} catch {
    Write-Host "✓ PASSED - Missing field rejected" -ForegroundColor Green
}
Write-Host ""

# Test 7: Save Valid Query
Write-Host "Test 7: Save Valid Query" -ForegroundColor Yellow
Write-Host "------------------------" -ForegroundColor Yellow
try {
    $body = @{
        name = "test_query_championship_wins"
        question = "Who won the most championships?"
        query = "SELECT driver, COUNT(*) as titles FROM drivers_championship WHERE position = '1' GROUP BY driver ORDER BY titles DESC LIMIT 10"
        summary = "Count championship wins by driver"
        tables_used = @("drivers_championship")
        data_quality_notes = "position field is TEXT type, use string comparison"
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri "$BaseUrl/mcp/tools/save_verified_query" `
        -Method Post `
        -ContentType "application/json" `
        -Headers @{"X-Archestra-Agent-Id"="test-agent"} `
        -Body $body
    
    Write-Host "✓ SUCCESS" -ForegroundColor Green
    $response | ConvertTo-Json
} catch {
    Write-Host "Note: Database may not be configured yet" -ForegroundColor Yellow
    Write-Host $_.Exception.Message
}
Write-Host ""

# Test 8: Invalid Query (DELETE - Should Fail)
Write-Host "Test 8: Invalid Query Type (Should Fail)" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow
try {
    $body = @{
        name = "bad_query"
        question = "Delete data"
        query = "DELETE FROM table WHERE id = 1"
    } | ConvertTo-Json
    
    $response = Invoke-RestMethod -Uri "$BaseUrl/mcp/tools/save_verified_query" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
    
    Write-Host "✗ FAILED - Should have rejected DELETE query" -ForegroundColor Red
} catch {
    Write-Host "✓ PASSED - DELETE query rejected" -ForegroundColor Green
}
Write-Host ""

# Test 9: Get Schema Resource
Write-Host "Test 9: Get Schema Resource" -ForegroundColor Yellow
Write-Host "---------------------------" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/mcp/resources/schema" -Method Get
    Write-Host "Tables tracked: $($response.tables.Count)" -ForegroundColor Green
} catch {
    Write-Host "Note: Knowledge base may not be loaded" -ForegroundColor Yellow
}
Write-Host ""

# Test 10: Get Learnings Resource
Write-Host "Test 10: Get Learnings Resource" -ForegroundColor Yellow
Write-Host "-------------------------------" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BaseUrl/mcp/resources/learnings" -Method Get
    Write-Host "Learnings count: $($response.count)" -ForegroundColor Green
} catch {
    Write-Host "Note: No learnings yet" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Tests Complete!" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
