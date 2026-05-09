# ODAP 全栈启动与测试脚本
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "ODAP 全栈启动与测试脚本" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 设置环境变量
$env:PYTHONPATH = "$PWD"
$env:ODAP_ENV = "development"

# 1. 检查 Python
Write-Host "[1/6] 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  Python: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  错误: 未找到 Python" -ForegroundColor Red
    exit 1
}

# 2. 安装 Python 依赖
Write-Host "[2/6] 安装 Python 依赖..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet 2>&1 | Out-Null
Write-Host "  依赖安装完成" -ForegroundColor Green

# 3. 启动后端服务
Write-Host "[3/6] 启动后端服务..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($pwd)
    Set-Location $pwd
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $PWD

Write-Host "  等待后端启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 检查后端是否启动
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 10
    Write-Host "  后端服务启动成功!" -ForegroundColor Green
} catch {
    Write-Host "  警告: 后端服务可能未完全启动，继续执行..." -ForegroundColor Yellow
}

# 4. 运行后端 API 测试
Write-Host "[4/6] 运行后端 API 集成测试..." -ForegroundColor Yellow
python -m pytest tests/integration/test_api_integration.py -v -s --tb=short --no-header -p no:warnings
$backendTestResult = $LASTEXITCODE
if ($backendTestResult -eq 0) {
    Write-Host "  后端测试全部通过!" -ForegroundColor Green
} else {
    Write-Host "  后端测试部分失败或跳过（可能是某些服务模块未就绪）" -ForegroundColor Yellow
}

# 5. 检查前端
Write-Host "[5/6] 检查前端环境..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  Node.js: $nodeVersion" -ForegroundColor Green
    
    Set-Location frontend
    Write-Host "  安装前端依赖..." -ForegroundColor Yellow
    npm install --silent 2>&1 | Out-Null
    
    Write-Host "  运行前端 API 集成测试..." -ForegroundColor Yellow
    npx vitest run src/test/api_integration.test.ts
    $frontendTestResult = $LASTEXITCODE
    Set-Location ..
    
    if ($frontendTestResult -eq 0) {
        Write-Host "  前端测试全部通过!" -ForegroundColor Green
    } else {
        Write-Host "  前端测试部分失败" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  信息: 未找到 Node.js，跳过前端测试" -ForegroundColor Yellow
}

# 6. 停止后端服务
Write-Host "[6/6] 停止后端服务..." -ForegroundColor Yellow
Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
Remove-Job -Job $backendJob -ErrorAction SilentlyContinue
Write-Host "  后端服务已停止" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "全栈测试完成" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan