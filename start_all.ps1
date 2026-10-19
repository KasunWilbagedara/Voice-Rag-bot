# Voice-RAG Bot - Windows PowerShell Launcher
# Launches:
# 1. Pure RAG Backend (Port 8000) in a new window
# 2. RAG with Tools Backend (Port 8001) in a new window
# 3. Next.js Frontend (Port 3000) in current window

$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

$python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🎙️  Starting Voice-RAG Bot Services (Windows)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Host "🚀 [1/3] Starting Pure RAG Backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ProjectRoot'; & '$python' -m backend_pure_rag.main"

Write-Host "🚀 [2/3] Starting RAG with Tools Backend on http://localhost:8001 ..." -ForegroundColor Magenta
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ProjectRoot'; & '$python' -m backend_with_tools.main"

Start-Sleep -Seconds 2

Write-Host "🚀 [3/3] Starting Next.js Frontend on http://localhost:3000 ..." -ForegroundColor Yellow
Write-Host "✨ Browser UI: http://localhost:3000" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

npm run dev
