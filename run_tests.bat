@echo off
echo ============================================
echo ODAP 全栈集成测试运行器
echo ============================================
echo.

REM 设置环境变量
set PYTHONPATH=%CD%

echo [1/4] 检查 Python 环境...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误: 未找到 Python
    exit /b 1
)
python --version
echo.

echo [2/4] 运行后端 API 集成测试...
python -m pytest tests/integration/test_api_integration.py -v -s --tb=short --no-header
if %ERRORLEVEL% NEQ 0 (
    echo 警告: 部分后端测试失败或跳过（可能是服务未启动）
)
echo.

echo [3/4] 检查前端环境...
where node >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 信息: 未找到 Node.js，跳过前端测试
    goto :done
)
cd frontend
echo 安装前端测试依赖...
call npm install --silent 2>nul
echo.

echo [4/4] 运行前端 API 集成测试...
call npx vitest run src/test/api_integration.test.ts
cd ..
echo.

:done
echo ============================================
echo 测试完成
echo ============================================