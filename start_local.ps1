Write-Host "=== ODAP 本地开发模式启动 ==="
Write-Host ""

Write-Host "1. 安装依赖..."
pip install -r requirements.txt

Write-Host ""
Write-Host "2. 启动 Web 服务..."
Write-Host ""
Write-Host "🌐 访问地址:"
Write-Host "   - API: http://localhost:8000"
Write-Host "   - API 文档: http://localhost:8000/docs"
Write-Host ""

python main.py --web